import os
import requests
from pathlib import Path
import logging
from playwright.sync_api import sync_playwright
from schemas import AnalyzeProductRequest
import time
import base64
import sys

try:
    from playwright._impl._errors import Error as PlaywrightError
except ImportError:
    PlaywrightError = Exception  # fallback if version changes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)

FIELDS_QUERY = '''
{
  page_validation {
    is_detail_page(Determine if this page focuses on a single specific product or item, not a category or list of multiple items.)
    reason(Explain briefly why this page is or isn’t identified as a single product detail page — mention clues like multiple prices, multiple product titles, or one clearly focused layout.)
  }
  product {
    title(The main visible name or heading of the single primary product on the page.)
    price(The active numeric selling price shown for that product, excluding old or discounted prices.)
    currency(The currency symbol or code displayed with the main price, such as $, USD, €, or GBP.)
    image_url(The URL of the main product image displayed on the page.)
  }
}
'''

def analyze_and_extract_product_data(params: AnalyzeProductRequest) -> dict:
    AGENTQL_API_KEY = os.getenv('AGENTQL_API_KEY')
    if not AGENTQL_API_KEY:
        logger.error("Missing AGENTQL_API_KEY in environment.")
        raise Exception("Missing AGENTQL_API_KEY in environment.")

    # Validate URL - reject chrome-extension:// and other non-http(s) URLs
    url = params.url.strip()
    if not url.startswith(('http://', 'https://')):
        error_msg = f"Invalid URL scheme. Expected http:// or https://, but received: {url}. Please provide the actual product page URL, not a chrome-extension:// URL."
        logger.error(error_msg)
        raise ValueError(error_msg)

    user_data_dir = str(Path.cwd() / "playwright-profile")
    screenshots_dir = Path.cwd() / "screens"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = None

    try:
        logger.info("Launching Playwright browser with frontend browser settings...")
        logger.info(f"Browser config - UserAgent: {params.userAgent}, Locale: {params.locale}, Timezone: {params.timezoneId}, AcceptLanguage: {params.acceptLanguage}, CountryCode: {params.countryCode}")
        
        with sync_playwright() as p:
            # Configure browser context to match frontend browser
            browser_context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome",
                headless=True,  # Run browser headless
                no_viewport=True,
                user_agent=params.userAgent,  # Set UA for all pages
                locale=params.locale,  # Set browser locale to match frontend
                timezone_id=params.timezoneId,  # Set timezone to match frontend
                extra_http_headers={
                    'Accept-Language': params.acceptLanguage,  # Set Accept-Language header
                },
            )
            pages = browser_context.pages
            if pages:
                page = pages[0]
            else:
                page = browser_context.new_page()
            
            # Set additional headers on the page to match frontend
            page.set_extra_http_headers({
                'Accept-Language': params.acceptLanguage,
            })
            
            logger.info(f"Navigating to {url} (wait_until=domcontentloaded) ...")
            page.goto(url, wait_until='domcontentloaded', timeout=60000)

            # --- Most reliable DOM stability logic ---
            QUIET_PERIOD = 4.0   # seconds of no DOM change (longer catches delayed XHR)
            MAX_WAIT = 25.0      # max seconds to wait for full page readiness
            STEP = 0.5
            last_html = None
            stable_for = 0.0
            total_wait = 0.0
            logger.info(f"Polling for DOM stability after domcontentloaded (max {MAX_WAIT}s, require {QUIET_PERIOD}s stable)...")
            while total_wait < MAX_WAIT:
                try:
                    current_html = page.content()
                except PlaywrightError:
                    logger.info("Waiting: page is navigating or changing, retrying in 200ms...")
                    time.sleep(0.2)
                    total_wait += 0.2
                    continue
                if last_html is None:
                    last_html = current_html
                    total_wait += STEP
                    time.sleep(STEP)
                    continue
                if current_html == last_html:
                    stable_for += STEP
                    if stable_for >= QUIET_PERIOD:
                        logger.info(f"DOM stable for {QUIET_PERIOD}s after {total_wait+STEP:.1f}s.")
                        break
                else:
                    stable_for = 0.0
                    last_html = current_html
                total_wait += STEP
                time.sleep(STEP)
            else:
                logger.warning(f"Max wait ({MAX_WAIT}s) reached, proceeding with current DOM.")

            #--- Grace period after stability ---
            GRACE_AFTER_STABLE = 2.5
            logger.info(f"Waiting extra {GRACE_AFTER_STABLE:.1f}s after perceived DOM stability for late JS or data...")
            time.sleep(GRACE_AFTER_STABLE)

            # Screenshot after all waiting
            timestamp = int(time.time())
            screenshot_path_obj = screenshots_dir / f"{timestamp}.png"
            screenshot_path = str(screenshot_path_obj)
            page.screenshot(path=screenshot_path, full_page=True)
            with open(screenshot_path, "rb") as imgfile:
                screenshot_b64 = base64.b64encode(imgfile.read()).decode()
            logger.info(f"Screenshot saved at {screenshot_path}")

            html = page.content()
            browser_context.close()

        logger.info("Posting to AgentQL API for extraction...")
        r = requests.post(
            'https://api.agentql.com/v1/query-data',
            json={
                'query': FIELDS_QUERY,
                'html': html,
                'params': { 'mode': 'fast' }
            },
            headers={
                'Content-Type': 'application/json',
                'x-api-key': AGENTQL_API_KEY
            }
        )
        if r.status_code != 200:
            logger.error(f"AgentQL error [{r.status_code}]: {r.text}")
            raise Exception(f"AgentQL error: {r.text}")
        agentql = r.json().get('data') or {}
        logger.info(f"Raw AgentQL response: {agentql}")

        # Construct response for frontend contract
        validation = {
            "isDetailPage": (agentql.get("page_validation", {}) or {}).get("is_detail_page"),
            "reason": (agentql.get("page_validation", {}) or {}).get("reason"),
        }
        prod = (agentql.get("product") or {})
        productData = {
            "title": prod.get("title"),
            "price_value": prod.get("price"),
            "currency": prod.get("currency"),
            "imageUrl": prod.get("image_url"),
        }
        result = {
            "validation": validation,
            "productData": productData
        }
        logger.info(f"Final frontend payload: {result}")
        return result
    except Exception as e:
        logger.exception("Error during analyze_and_extract_product_data execution:")
        raise
