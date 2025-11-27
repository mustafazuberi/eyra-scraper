import os
import re
import requests
import logging
from typing import Dict, Any, Optional, Union
from playwright.sync_api import Page
from parsel import Selector
from lxml import etree

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


def _normalize_text(text: str) -> str:
    """Normalize text for comparison by removing extra whitespace."""
    return " ".join(text.split()) if text else ""


def _get_xpath_from_element(selector: Selector, element) -> Optional[str]:
    """Get XPath from a parsel element using underlying lxml."""
    try:
        # Get the underlying lxml element from parsel
        # Parsel elements have a .root attribute pointing to lxml element
        if not hasattr(element, 'root'):
            return None
        
        lxml_elem = element.root
        if lxml_elem is None:
            return None
        
        # Create ElementTree from selector's root to use getpath()
        root = selector.root
        if root is not None:
            tree = etree.ElementTree(root)
            return tree.getpath(lxml_elem)
        return None
    except Exception as e:
        logger.debug(f"Failed to get XPath from element: {e}")
        return None


def _extract_numeric_value(price_str: Union[str, float]) -> float:
    if isinstance(price_str, (int, float)):
        return float(price_str)
    
    # Remove currency symbols and extract numbers
    price_clean = re.sub(r'[^\d.,]', '', str(price_str))
    # Handle different decimal separators
    price_clean = price_clean.replace(',', '.')
    # Remove multiple dots, keep only the last one as decimal
    parts = price_clean.split('.')
    if len(parts) > 2:
        price_clean = ''.join(parts[:-1]) + '.' + parts[-1]
    
    try:
        return float(price_clean)
    except ValueError:
        return 0.0


def _find_title_selector(selector: Selector, title: str) -> Optional[str]:
    """Find XPath selector for element containing the product title."""
    if not title:
        return None
    
    title_normalized = _normalize_text(title.lower())
    title_words = [w for w in title_normalized.split() if len(w) > 2]
    
    if not title_words:
        return None
    
    # Strategy 1: Try heading elements first (h1, h2, h3, h4)
    for tag in ['h1', 'h2', 'h3', 'h4']:
        for elem in selector.css(tag):
            text = _normalize_text(elem.get()).lower()
            if title_normalized in text or text in title_normalized:
                xpath = _get_xpath_from_element(selector, elem)
                if xpath:
                    return xpath
            # Check for significant word overlap
            if len(title_words) >= 3:
                text_words = set(w for w in text.split() if len(w) > 2)
                if len(set(title_words) & text_words) >= 3:
                    xpath = _get_xpath_from_element(selector, elem)
                    if xpath:
                        return xpath
    
    # Strategy 2: Search all elements with product-related classes/ids
    for xpath_query in [
        "//*[contains(@class, 'product') or contains(@class, 'title') or contains(@class, 'name')]",
        "//*[contains(@id, 'product') or contains(@id, 'title') or contains(@id, 'name')]",
    ]:
        for elem in selector.xpath(xpath_query):
            text = _normalize_text(elem.get()).lower()
            if title_normalized in text or text in title_normalized:
                xpath = _get_xpath_from_element(selector, elem)
                if xpath:
                    return xpath
    
    # Strategy 3: Search all elements for text match
    xpath_query = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{title_normalized[:30]}')]"
    try:
        matches = selector.xpath(xpath_query)
        if matches:
            # Return first match
            xpath = _get_xpath_from_element(selector, matches[0])
            if xpath:
                return xpath
    except:
        pass
    
    return None


def _find_price_selector(selector: Selector, price: Union[str, float]) -> Optional[str]:
    """Find XPath selector for element containing the product price."""
    if price is None:
        return None
    
    price_value = _extract_numeric_value(price)
    if price_value == 0:
        return None
    
    price_str = str(price_value)
    price_int = str(int(price_value))
    price_formatted = f"{price_value:.2f}".rstrip('0').rstrip('.')
    
    # Strategy 1: Search elements with price-related classes/ids
    for xpath_query in [
        "//*[contains(@class, 'price') or contains(@class, 'cost') or contains(@class, 'amount')]",
        "//*[contains(@id, 'price') or contains(@id, 'cost') or contains(@id, 'amount')]",
    ]:
        for elem in selector.xpath(xpath_query):
            text = _normalize_text(elem.get())
            if price_str in text or price_formatted in text or price_int in text:
                xpath = _get_xpath_from_element(selector, elem)
                if xpath:
                    return xpath
    
    # Strategy 2: Search for elements containing the price number
    # Try exact match first
    for price_val in [price_str, price_formatted, price_int]:
        xpath_query = f"//*[contains(text(), '{price_val}')]"
        try:
            matches = selector.xpath(xpath_query)
            if matches:
                # Prefer elements with currency symbols
                for match in matches:
                    text = _normalize_text(match.get())
                    if re.search(r'[$€£¥₹]|USD|EUR|GBP', text):
                        xpath = _get_xpath_from_element(selector, match)
                        if xpath:
                            return xpath
                # Return first match if no currency found
                xpath = _get_xpath_from_element(selector, matches[0])
                if xpath:
                    return xpath
        except:
            continue
    
    return None


def _find_currency_selector(selector: Selector, currency: str, price_xpath: Optional[str] = None) -> Optional[str]:
    """Find XPath selector for element containing the currency symbol."""
    if not currency:
        return None
    
    currency_clean = currency.strip().upper()
    currency_symbols = {
        'USD': ['$', 'usd', 'dollar'],
        'EUR': ['€', 'eur', 'euro'],
        'GBP': ['£', 'gbp', 'pound'],
        'JPY': ['¥', 'jpy', 'yen'],
        'INR': ['₹', 'inr', 'rupee'],
    }
    
    # Get all possible currency representations
    search_terms = [currency_clean]
    for key, values in currency_symbols.items():
        if currency_clean == key or currency_clean in values:
            search_terms.extend(values)
            break
    
    # Strategy 1: If price xpath exists, check nearby elements
    if price_xpath:
        try:
            price_elem = selector.xpath(price_xpath)
            if price_elem:
                # Check price element itself
                text = _normalize_text(price_elem.get()).upper()
                if any(term.upper() in text for term in search_terms):
                    return price_xpath
                
                # Check parent
                parent = price_elem.xpath('..')
                if parent:
                    parent_text = _normalize_text(parent.get()).upper()
                    if any(term.upper() in parent_text for term in search_terms):
                        xpath = _get_xpath_from_element(selector, parent)
                        if xpath:
                            return xpath
                
                # Check preceding/following siblings
                for sibling_xpath_query in [f"{price_xpath}/preceding-sibling::*[1]", f"{price_xpath}/following-sibling::*[1]"]:
                    try:
                        sibling = selector.xpath(sibling_xpath_query)
                        if sibling:
                            sibling_text = _normalize_text(sibling.get()).upper()
                            if any(term.upper() in sibling_text for term in search_terms):
                                xpath = _get_xpath_from_element(selector, sibling)
                                if xpath:
                                    return xpath
                    except:
                        continue
        except:
            pass
    
    # Strategy 2: Search for currency symbol in elements with price-related classes
    for xpath_query in [
        "//*[contains(@class, 'price') or contains(@class, 'currency')]",
        "//*[contains(@id, 'price') or contains(@id, 'currency')]",
    ]:
        for elem in selector.xpath(xpath_query):
            text = _normalize_text(elem.get()).upper()
            if any(term.upper() in text for term in search_terms):
                xpath = _get_xpath_from_element(selector, elem)
                if xpath:
                    return xpath
    
    # Strategy 3: Search for currency symbol directly
    for term in search_terms:
        if len(term) == 1:  # Single character symbol
            xpath_query = f"//*[contains(text(), '{term}')]"
        else:  # Currency code
            xpath_query = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{term.lower()}')]"
        try:
            matches = selector.xpath(xpath_query)
            if matches:
                xpath = _get_xpath_from_element(selector, matches[0])
                if xpath:
                    return xpath
        except:
            continue
    
    return None


def extract_values_with_selectors(html: str, selectors: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    """
    Extract values from HTML using XPath selectors.
    
    Args:
        html: Full HTML content of the rendered page
        selectors: Dictionary with XPath selectors:
            {
                "title_xpath": "...",
                "price_xpath": "...",
                "currency_xpath": "..."
            }
    
    Returns:
        Dictionary with extracted values:
        {
            "title": "...",
            "price": "...",
            "currency": "..."
        }
    """
    result = {
        "title": None,
        "price": None,
        "currency": None,
    }
    
    try:
        selector = Selector(text=html)
        
        # Extract title - get text content only, not HTML
        if selectors.get("title_xpath"):
            try:
                title_elem = selector.xpath(selectors["title_xpath"])
                if title_elem:
                    # Use XPath text() to get only text content, not HTML tags
                    title_text = title_elem.xpath(".//text()").getall()
                    if title_text:
                        # Join all text nodes and normalize
                        result["title"] = _normalize_text(" ".join(title_text))
                    else:
                        # Fallback: try to get text directly
                        result["title"] = _normalize_text(title_elem.get())
            except Exception as e:
                logger.warning(f"Failed to extract title with XPath: {e}")
        
        # Extract price - be smarter about finding the actual price
        if selectors.get("price_xpath"):
            try:
                price_elem = selector.xpath(selectors["price_xpath"])
                if price_elem:
                    price_text = _normalize_text(price_elem.get())
                    # Look for price patterns: numbers with decimals, near currency symbols
                    # Pattern: currency symbol followed by number, or number with 1-2 decimal places
                    price_patterns = [
                        r'([$€£¥₹])\s*(\d+\.?\d*)',  # Currency symbol + number
                        r'(\d+\.\d{1,2})\b',  # Decimal number with 1-2 decimal places
                        r'(\d+,\d{1,2})\b',  # Decimal number with comma separator
                    ]
                    
                    price_value = None
                    for pattern in price_patterns:
                        matches = re.findall(pattern, price_text)
                        if matches:
                            # Get the first match
                            if isinstance(matches[0], tuple):
                                # Pattern with groups (currency + number)
                                price_str = matches[0][1] if len(matches[0]) > 1 else matches[0][0]
                            else:
                                price_str = matches[0]
                            
                            # Clean and convert
                            price_clean = price_str.replace(',', '.')
                            try:
                                price_value = float(price_clean)
                                # Reasonable price range check (0.01 to 1,000,000)
                                if 0.01 <= price_value <= 1000000:
                                    result["price"] = price_value
                                    break
                            except ValueError:
                                continue
                    
                    # Fallback: if no pattern matched, try the old method but be more careful
                    if result["price"] is None:
                        # Try to find the smallest reasonable number (likely the price)
                        all_numbers = re.findall(r'\d+\.?\d*', price_text)
                        for num_str in all_numbers:
                            try:
                                num_val = float(num_str)
                                if 0.01 <= num_val <= 1000000:
                                    result["price"] = num_val
                                    break
                            except ValueError:
                                continue
            except Exception as e:
                logger.warning(f"Failed to extract price with XPath: {e}")
        
        # Extract currency
        if selectors.get("currency_xpath"):
            try:
                currency_elem = selector.xpath(selectors["currency_xpath"])
                if currency_elem:
                    currency_text = _normalize_text(currency_elem.get())
                    # Extract currency symbol/code
                    currency_match = re.search(r'([$€£¥₹]|USD|EUR|GBP|JPY|INR)', currency_text, re.IGNORECASE)
                    if currency_match:
                        result["currency"] = currency_match.group(1)
                    else:
                        result["currency"] = currency_text.strip()
            except Exception as e:
                logger.warning(f"Failed to extract currency with XPath: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error extracting values with selectors: {str(e)}")
        return result


def compare_selectors_with_agentql(
    html: str,
    selectors: Dict[str, Optional[str]],
    agentql_values: Dict[str, Any]
) -> Dict[str, Any]:
    # Extract values using XPath selectors
    xpath_values = extract_values_with_selectors(html, selectors)
    
    # Normalize AgentQL values for comparison
    agentql_normalized = {
        "title": _normalize_text(str(agentql_values.get("title", ""))) if agentql_values.get("title") else None,
        "price": _extract_numeric_value(agentql_values.get("price")) if agentql_values.get("price") is not None else None,
        "currency": str(agentql_values.get("currency", "")).strip() if agentql_values.get("currency") else None,
    }
    
    # Normalize XPath values for comparison
    xpath_normalized = {
        "title": xpath_values.get("title"),
        "price": _extract_numeric_value(xpath_values.get("price")) if xpath_values.get("price") else None,
        "currency": str(xpath_values.get("currency", "")).strip() if xpath_values.get("currency") else None,
    }
    
    # Compare values
    matches = {
        "title": False,
        "price": False,
        "currency": False,
    }
    
    # Compare title (case-insensitive, allow partial match)
    if agentql_normalized["title"] and xpath_normalized["title"]:
        agentql_title_lower = agentql_normalized["title"].lower()
        xpath_title_lower = xpath_normalized["title"].lower()
        # Exact match or one contains the other (for cases where XPath gets more/less text)
        matches["title"] = (
            agentql_title_lower == xpath_title_lower or
            agentql_title_lower in xpath_title_lower or
            xpath_title_lower in agentql_title_lower
        )
    
    # Compare price (allow small floating point differences)
    if agentql_normalized["price"] is not None and xpath_normalized["price"] is not None:
        price_diff = abs(float(agentql_normalized["price"]) - float(xpath_normalized["price"]))
        matches["price"] = price_diff < 0.01  # Allow 1 cent difference
    
    # Compare currency (case-insensitive)
    if agentql_normalized["currency"] and xpath_normalized["currency"]:
        agentql_currency_upper = agentql_normalized["currency"].upper()
        xpath_currency_upper = xpath_normalized["currency"].upper()
        matches["currency"] = agentql_currency_upper == xpath_currency_upper
    
    all_match = all(matches.values())
    
    result = {
        "xpath_values": xpath_values,
        "agentql_values": agentql_values,
        "matches": matches,
        "all_match": all_match,
    }
    
    logger.info(f"Selector comparison: {result}")
    return result


def extract_selectors(html: str, title: str, price: Union[float, str], currency: str) -> Dict[str, Optional[str]]:
    """
    Extract XPath selectors for product title, price, and currency from HTML.
    
    These selectors can be stored in the database and reused for scheduled price checks
    without calling AgentQL again. Use them with Playwright like:
    
        title = page.locator(selectors["title_xpath"]).inner_text()
        price = page.locator(selectors["price_xpath"]).inner_text()
        currency = page.locator(selectors["currency_xpath"]).inner_text()
    
    Args:
        html: Full HTML content of the rendered page
        title: Product title string
        price: Product price as string or numeric value
        currency: Currency symbol or code (e.g., '$', 'USD', '€')
    
    Returns:
        Dictionary with XPath selectors:
        {
            "title_xpath": "...",
            "price_xpath": "...",
            "currency_xpath": "..."
        }
    """
    try:
        # Parse HTML with parsel
        selector = Selector(text=html)
        
        # Find XPath selectors
        title_xpath = _find_title_selector(selector, title)
        price_xpath = _find_price_selector(selector, price)
        currency_xpath = _find_currency_selector(selector, currency, price_xpath)
        
        result = {
            "title_xpath": title_xpath,
            "price_xpath": price_xpath,
            "currency_xpath": currency_xpath,
        }
        
        logger.info(f"Extracted selectors: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error extracting selectors: {str(e)}")
        # Return empty selectors on error
        return {
            "title_xpath": None,
            "price_xpath": None,
            "currency_xpath": None,
        }
