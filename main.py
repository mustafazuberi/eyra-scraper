import traceback
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from schemas import (
    AnalyzeProductRequest,
    ValidateProductRequest,
    ScrapeProductRequest,
)
from services import (
    analyze_and_extract_product_data,
    validate_product_page,
    scrape_product_data,
    validate_product_page_from_html,
    scrape_product_data_from_html,
)
from utils.response import create_success_response, create_error_response
from constants import HTTP_STATUS, ERROR_CODES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()


app = FastAPI(
    title="Product Scraper API",
    description="API for validating and scraping product data from web pages",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_message = str(exc)
    traceback_str = traceback.format_exc()
    
    logger.error(f"Unhandled exception: {error_message}\n{traceback_str}")
    
    return create_error_response(
        code=ERROR_CODES["SERVER_ERROR"],
        message=f"Internal server error: {error_message}",
        status_code=HTTP_STATUS["INTERNAL_SERVER_ERROR"],
    )


def handle_api_error(operation: str, error: Exception):
    error_message = str(error)
    traceback_str = traceback.format_exc()
    
    logger.error(f"HTTP 500 Error during {operation}: {error_message}\n{traceback_str}")
    
    # Determine error code based on error type
    if "Invalid URL" in error_message or "URL" in error_message:
        error_code = ERROR_CODES["INVALID_URL"]
        status_code = HTTP_STATUS["BAD_REQUEST"]
    elif "AGENTQL" in error_message or "AgentQL" in error_message:
        error_code = ERROR_CODES["AGENTQL_ERROR"]
        status_code = HTTP_STATUS["INTERNAL_SERVER_ERROR"]
    elif "proxy" in error_message.lower():
        error_code = ERROR_CODES["PROXY_ERROR"]
        status_code = HTTP_STATUS["SERVICE_UNAVAILABLE"]
    else:
        error_code = ERROR_CODES["SERVER_ERROR"]
        status_code = HTTP_STATUS["INTERNAL_SERVER_ERROR"]
    
    return create_error_response(
        code=error_code,
        message=f"Failed to {operation}: {error_message}",
        status_code=status_code,
        details={"traceback": traceback_str} if logger.level <= logging.DEBUG else None,
    )


@app.post("/api/product/validate")
def validate_product_page_endpoint(request: ValidateProductRequest):
    try:
        validation_result = validate_product_page_from_html(request)
        response = create_success_response(
            data=validation_result,
            message="Page validation completed successfully",
        )
        return response
    except Exception as e:
        response = handle_api_error("validate product page", e)
        return response


@app.post("/api/product/scrape")
def scrape_product_data_endpoint(request: ScrapeProductRequest):
    try:
        product_data = scrape_product_data_from_html(request)
        response = create_success_response(
            data=product_data,
            message="Product data scraped successfully",
        )
        return response
    except Exception as e:
        response = handle_api_error("scrape product data", e)
        return response


@app.post("/api/product/analyze-and-scrape")
def analyze_and_extract_product_data_endpoint(request: AnalyzeProductRequest):
    try:
        result = analyze_and_extract_product_data(request)
        response = create_success_response(
            data=result,
            message="Product analysis completed successfully",
        )
        return response
    except Exception as e:
        response = handle_api_error("analyze product", e)
        return response
