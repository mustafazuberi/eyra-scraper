import os
import requests
import logging
from typing import Dict, Any
from playwright.sync_api import Page

logger = logging.getLogger(__name__)

VALIDATION_QUERY = """
{
  is_detail_page(Determine if this page focuses on a single specific product or item, not a category or list of multiple items.)
  reason(Explain briefly why this page is or isn't identified as a single product detail page — mention clues like multiple prices, multiple product titles, or one clearly focused layout.)
}
"""

SCRAPE_PRODUCT_QUERY = """
{
  title(The main visible name or heading of the single primary product on the page.)
  price(The active numeric selling price shown for that product, excluding old or discounted prices.)
  currency(The currency symbol or code displayed with the main price, such as $, USD, €, or GBP.)
  image_url(The URL of the main product image displayed on the page.)
}
"""

COMBINED_QUERY = """
{
  page_validation {
    is_detail_page(Determine if this page focuses on a single specific product or item, not a category or list of multiple items.)
    reason(Explain briefly why this page is or isn't identified as a single product detail page — mention clues like multiple prices, multiple product titles, or one clearly focused layout.)
  }
  product {
    title(The main visible name or heading of the single primary product on the page.)
    price(The active numeric selling price shown for that product, excluding old or discounted prices.)
    currency(The currency symbol or code displayed with the main price, such as $, USD, €, or GBP.)
    image_url(The URL of the main product image displayed on the page.)
  }
}
"""


def query_agentql_data(query: str, html_content: str) -> Dict:
    agentql_api_key = os.getenv("AGENTQL_API_KEY")
    
    if not agentql_api_key:
        logger.error("Missing AGENTQL_API_KEY in environment.")
        raise Exception("Missing AGENTQL_API_KEY in environment.")

    logger.info("Posting to AgentQL REST API for data extraction...")
    
    response = requests.post(
        "https://api.agentql.com/v1/query-data",
        json={"query": query, "html": html_content, "params": {"mode": "fast"}},
        headers={"Content-Type": "application/json", "x-api-key": agentql_api_key},
    )

    if response.status_code != 200:
        logger.error(f"AgentQL error [{response.status_code}]: {response.text}")
        raise Exception(f"AgentQL error: {response.text}")

    agentql_data = response.json().get("data") or {}
    
    logger.info(f"Raw AgentQL data response: {agentql_data}")
    
    return agentql_data


def query_agentql_elements(query: str, page: Page) -> Any:
    try:
        import agentql
    except ImportError:
        logger.error("AgentQL Python SDK not installed. Install with: pip install agentql")
        raise Exception("AgentQL Python SDK not installed. Install with: pip install agentql")
    
    agentql_api_key = os.getenv("AGENTQL_API_KEY")
    
    if not agentql_api_key:
        logger.error("Missing AGENTQL_API_KEY in environment.")
        raise Exception("Missing AGENTQL_API_KEY in environment.")

    logger.info("Querying AgentQL for interactive elements using Python SDK...")
    
    try:
        agentql_page = agentql.wrap(page)
        
        response = agentql_page.query_elements(query)
        
        logger.info("AgentQL elements query completed successfully")
        
        return response
        
    except Exception as e:
        logger.error(f"AgentQL query_elements error: {str(e)}")
        raise Exception(f"AgentQL query_elements error: {str(e)}")
