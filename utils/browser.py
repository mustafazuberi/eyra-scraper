import time
import logging
from typing import Tuple
from playwright.sync_api import Playwright, Browser, BrowserContext, Page
from playwright_stealth import stealth_sync

try:
    from playwright._impl._errors import Error as PlaywrightError
except ImportError:
    PlaywrightError = Exception  # fallback if version changes

logger = logging.getLogger(__name__)


def setup_browser_with_proxy_and_stealth(
    playwright_instance: Playwright,
    user_agent: str,
    locale: str,
    accept_language: str,
    proxy_config: dict,
) -> Tuple[Browser, BrowserContext, Page]:
    browser = playwright_instance.chromium.launch(
        channel="chrome",
        headless=True,
        args=[
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-setuid-sandbox",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )

    browser_context = browser.new_context(
        user_agent=user_agent,
        locale=locale,
        proxy={
            "server": proxy_config["server"],
            "username": proxy_config["username"],
            "password": proxy_config["password"],
        },
        extra_http_headers={
            "Accept-Language": accept_language,
        },
    )

    page = browser_context.new_page()
    stealth_sync(page)
    page.set_extra_http_headers({"Accept-Language": accept_language})

    def handle_route(route):
        resource_type = route.request.resource_type
        if resource_type in ["image", "media", "font"]:
            route.abort()
        else:
            route.continue_()

    page.route("**/*", handle_route)

    return browser, browser_context, page


def wait_for_dom_stability(
    page: Page,
    quiet_period_seconds: float = 4.0,
    max_wait_seconds: float = 25.0,
) -> str:
    step_interval = 0.5
    last_html_content = None
    stable_duration = 0.0
    total_wait_time = 0.0

    logger.info(
        f"Polling for DOM stability (max {max_wait_seconds}s, require {quiet_period_seconds}s stable)..."
    )

    while total_wait_time < max_wait_seconds:
        try:
            current_html_content = page.content()
        except PlaywrightError:
            logger.info("Waiting: page is navigating or changing, retrying in 200ms...")
            time.sleep(0.2)
            total_wait_time += 0.2
            continue

        if last_html_content is None:
            last_html_content = current_html_content
            total_wait_time += step_interval
            time.sleep(step_interval)
            continue

        if current_html_content == last_html_content:
            stable_duration += step_interval
            if stable_duration >= quiet_period_seconds:
                logger.info(
                    f"DOM stable for {quiet_period_seconds}s after {total_wait_time+step_interval:.1f}s."
                )
                break
        else:
            stable_duration = 0.0
            last_html_content = current_html_content

        total_wait_time += step_interval
        time.sleep(step_interval)
    else:
        logger.warning(
            f"Max wait ({max_wait_seconds}s) reached, proceeding with current DOM."
        )

    # Grace period after stability
    grace_period_seconds = 2.5
    logger.info(
        f"Waiting extra {grace_period_seconds:.1f}s after perceived DOM stability for late JS or data..."
    )
    time.sleep(grace_period_seconds)

    return page.content()
