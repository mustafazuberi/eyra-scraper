import logging
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from schemas import AnalyzeProductRequest, ValidateProductRequest, ScrapeProductRequest

# Import utilities
from utils.proxy import generate_proxy_config
from utils.validation import validate_url
from utils.browser import setup_browser_with_proxy_and_stealth, wait_for_dom_stability
from utils.agentql import (
    VALIDATION_QUERY,
    SCRAPE_PRODUCT_QUERY,
    COMBINED_QUERY,
    extract_selectors,
    extract_values_with_selectors,
    query_agentql_data,
    query_agentql_elements,
    compare_selectors_with_agentql,
)

logger = logging.getLogger(__name__)


def validate_product_page_from_html(params: ValidateProductRequest) -> dict:
    html_content = params.html
    
    if not html_content or not html_content.strip():
        raise ValueError("HTML content is required and cannot be empty")
    
    logger.info("Validating product page from HTML content")
    
    try:
        agentql_data = query_agentql_data(VALIDATION_QUERY, html_content)
        
        validation_result = {
            "isDetailPage": agentql_data.get("is_detail_page", False),
            "reason": agentql_data.get("reason", "Unable to determine page type."),
        }
        
        logger.info(f"Validation result: {validation_result}")
        return validation_result
        
    except Exception as e:
        logger.exception("Error during validate_product_page_from_html execution:")
        raise


def scrape_product_data_from_html(params: ScrapeProductRequest) -> dict:
    html_content = params.html
    
    if not html_content or not html_content.strip():
        raise ValueError("HTML content is required and cannot be empty")
    
    try:
        scraped_data = query_agentql_data(SCRAPE_PRODUCT_QUERY, html_content)
        
        product_data = {
            "title": scraped_data.get("title"),
            "price": scraped_data.get("price"),
            "currency": scraped_data.get("currency"),
        }

        selectors = extract_selectors(html_content, product_data.get("title"), product_data.get("price"), product_data.get("currency"))

        logger.info(f"Selectors: {selectors}")
        logger.info(f"AgentQL elements response: {product_data}")
        
        # Extract values using XPath selectors
        xpath_values = extract_values_with_selectors(html_content, selectors)
        
        # Compare XPath selectors with AgentQL values to verify they match
        if all(selectors.values()):  # Only compare if all selectors were found
            comparison = compare_selectors_with_agentql(html_content, selectors, product_data)
            logger.info(f"Selector comparison result: matches={comparison['matches']}, all_match={comparison['all_match']}")
            
            if not comparison["all_match"]:
                logger.warning(
                    f"XPath selectors don't fully match AgentQL values. "
                    f"XPath values: {comparison['xpath_values']}, "
                    f"AgentQL values: {comparison['agentql_values']}, "
                    f"Matches: {comparison['matches']}"
                )
        else:
            logger.warning("Not all selectors were found, skipping comparison")
        
        # Return values extracted with selectors along with their selectors
        result = {
            "title": {
                "value": xpath_values.get("title") or product_data.get("title"),
                "selector": selectors.get("title_xpath"),
            },
            "price": {
                "value": xpath_values.get("price") or product_data.get("price"),
                "selector": selectors.get("price_xpath"),
            },
            "currency": {
                "value": xpath_values.get("currency") or product_data.get("currency"),
                "selector": selectors.get("currency_xpath"),
            },
        }
        
        return result
    finally:
        pass


def validate_product_page(params: AnalyzeProductRequest) -> dict:
    url = validate_url(params.url)
    proxy_config = generate_proxy_config(params.countryCode or "US")

    logger.info(f"Validating product page: {url}")
    logger.info(
        f"Browser config - UserAgent: {params.userAgent}, "
        f"Locale: {params.locale}, CountryCode: {params.countryCode}"
    )

    playwright_instance = None
    browser = None
    try:
        playwright_instance = sync_playwright().start()
        browser, browser_context, page = setup_browser_with_proxy_and_stealth(
            playwright_instance=playwright_instance,
            user_agent=params.userAgent,
            locale=params.locale,
            accept_language=params.acceptLanguage,
            proxy_config=proxy_config,
        )

        logger.info(f"Navigating to {url} (wait_until=domcontentloaded) ...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        html_content = wait_for_dom_stability(page)
        agentql_data = query_agentql_data(VALIDATION_QUERY, html_content)

        validation_result = {
            "isDetailPage": agentql_data.get("is_detail_page", False),
            "reason": agentql_data.get("reason", "Unable to determine page type."),
        }

        logger.info(f"Validation result: {validation_result}")
        return validation_result

    except Exception as e:
        logger.exception("Error during validate_product_page execution:")
        raise
    finally:
        if browser:
            browser.close()
        if playwright_instance:
            playwright_instance.stop()


def scrape_product_data(params: AnalyzeProductRequest) -> dict:
    url = validate_url(params.url)
    proxy_config = generate_proxy_config(params.countryCode or "US")

    logger.info(f"Scraping product data from: {url}")
    logger.info(
        f"Browser config - UserAgent: {params.userAgent}, "
        f"Locale: {params.locale}, CountryCode: {params.countryCode}"
    )

    playwright_instance = None
    browser = None
    try:
        playwright_instance = sync_playwright().start()
        browser, browser_context, page = setup_browser_with_proxy_and_stealth(
            playwright_instance=playwright_instance,
            user_agent=params.userAgent,
            locale=params.locale,
            accept_language=params.acceptLanguage,
            proxy_config=proxy_config,
        )

        logger.info(f"Navigating to {url} (wait_until=domcontentloaded) ...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        html_content = wait_for_dom_stability(page)
        agentql_data = query_agentql_data(SCRAPE_PRODUCT_QUERY, html_content)

        product_data = {
            "title": agentql_data.get("title"),
            "price_value": agentql_data.get("price"),
            "currency": agentql_data.get("currency"),
            "imageUrl": agentql_data.get("image_url"),
        }

        logger.info(f"Scraped product data: {product_data}")
        return product_data

    except Exception as e:
        logger.exception("Error during scrape_product_data execution:")
        raise
    finally:
        if browser:
            browser.close()
        if playwright_instance:
            playwright_instance.stop()


def analyze_and_extract_product_data(params: AnalyzeProductRequest) -> dict:
    
    url = validate_url(params.url)
    proxy_config = generate_proxy_config(params.countryCode or "US")

    logger.info("Launching Playwright browser with frontend browser settings...")
    logger.info(
        f"Browser config - UserAgent: {params.userAgent}, "
        f"Locale: {params.locale}, Timezone: {params.timezoneId}, "
        f"AcceptLanguage: {params.acceptLanguage}, CountryCode: {params.countryCode}"
    )
    logger.info(
        f"Proxy config - Server: {proxy_config['server']}, "
        f"Username: {proxy_config['username']}, Country: {params.countryCode}"
    )

    screenshots_dir = Path.cwd() / "screens"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    playwright_instance = None
    browser = None
    try:
        playwright_instance = sync_playwright().start()
        browser, browser_context, page = setup_browser_with_proxy_and_stealth(
            playwright_instance=playwright_instance,
            user_agent=params.userAgent,
            locale=params.locale,
            accept_language=params.acceptLanguage,
            proxy_config=proxy_config,
        )

        logger.info(f"Navigating to {url} (wait_until=domcontentloaded) ...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        html_content = wait_for_dom_stability(page)

        # Take screenshot
        timestamp = int(time.time())
        screenshot_path = screenshots_dir / f"{timestamp}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Screenshot saved at {screenshot_path}")

        agentql_data = query_agentql_data(COMBINED_QUERY, html_content)

        # Construct response for frontend contract
        validation = {
            "isDetailPage": (agentql_data.get("page_validation", {}) or {}).get(
                "is_detail_page"
            ),
            "reason": (agentql_data.get("page_validation", {}) or {}).get("reason"),
        }
        product = agentql_data.get("product") or {}
        productData = {
            "title": product.get("title"),
            "price_value": product.get("price"),
            "currency": product.get("currency"),
            "imageUrl": product.get("image_url"),
        }
        result = {"validation": validation, "productData": productData}
        logger.info(f"Final frontend payload: {result}")
        return result

    except Exception as e:
        logger.exception("Error during analyze_and_extract_product_data execution:")
        raise
    finally:
        if browser:
            browser.close()
        if playwright_instance:
            playwright_instance.stop()
