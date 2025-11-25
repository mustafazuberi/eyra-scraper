import logging

logger = logging.getLogger(__name__)

def validate_url(url: str) -> str:
    sanitized_url = url.strip()
    
    if not sanitized_url.startswith(("http://", "https://")):
        error_msg = (
            f"Invalid URL scheme. Expected http:// or https://, but received: {sanitized_url}. "
            "Please provide the actual product page URL, not a chrome-extension:// URL."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return sanitized_url
