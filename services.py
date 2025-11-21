import os
import requests
from pathlib import Path
import logging
from playwright.sync_api import sync_playwright
from schemas import AnalyzeProductRequest
import time

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

    user_data_dir = str(Path.cwd() / "playwright-profile")

    try:
        logger.info("Launching Playwright browser...")
        with sync_playwright() as p:
            browser_context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome",
                headless=True,  # Run browser headless
                no_viewport=True,
                user_agent=params.userAgent,  # Set UA for all pages
            )
            pages = browser_context.pages
            if pages:
                page = pages[0]
            else:
                page = browser_context.new_page()
            logger.info(f"Navigating to {params.url} ...")
            page.goto(params.url, wait_until='domcontentloaded', timeout=60000)

            # DOM stability detection
            QUIET_PERIOD = 2.0
            MAX_WAIT = 15.0
            STEP = 0.5
            last_html = page.content()
            stable_for = 0.0
            total_wait = 0.0
            logger.info(f"Waiting for DOM stability (max {MAX_WAIT}s)...")
            while total_wait < MAX_WAIT:
                time.sleep(STEP)
                current_html = page.content()
                if current_html == last_html:
                    stable_for += STEP
                    if stable_for >= QUIET_PERIOD:
                        logger.info(f"DOM stable for {QUIET_PERIOD}s after {total_wait+STEP:.1f}s.")
                        break
                else:
                    stable_for = 0.0
                    last_html = current_html
                total_wait += STEP
            else:
                logger.warning(f"Max wait ({MAX_WAIT}s) reached, proceeding with current DOM.")
            html = current_html
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
        data = r.json().get('data')
        logger.info(f"Raw AgentQL response: {data}")
        # Pass-through: no pydantic wrapping/validation!
        return data
    except Exception as e:
        logger.exception("Error during analyze_and_extract_product_data execution:")
        raise
