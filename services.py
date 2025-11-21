import os
import requests
from pathlib import Path
import logging
from playwright.sync_api import sync_playwright
from schemas import AnalyzeProductRequest, ProductAnalysisResult, Validation
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

def analyze_and_extract_product_data(params: AnalyzeProductRequest) -> ProductAnalysisResult:
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
        data = r.json().get('data')
        logger.info(f"Raw AgentQL response: {data}")
        validation = Validation(
            isDetailPage=data['page_validation']['is_detail_page'],
            reason=data['page_validation']['reason'],
        )
        pd = data['product']
        product_data = None
        if pd:
            product_data = {
                'title': pd.get('title'),
                'price_value': pd.get('price'),
                'currency': pd.get('currency'),
                'imageUrl': pd.get('image_url'),
            }
        logger.info(f"Parsed product_data: {product_data}")
        result = ProductAnalysisResult(validation=validation, productData=product_data)
        logger.info(f"Final API response to frontend: {result}")
        return result
    except Exception as e:
        logger.exception("Error during analyze_and_extract_product_data execution:")
        raise
