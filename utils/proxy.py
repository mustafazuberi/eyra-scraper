"""
Proxy configuration utilities.
"""
from typing import Dict


def generate_proxy_config(country_code: str = "US") -> Dict[str, str]:
    username = "mustafazub4"
    password = f"bFdWY6V7WXjAIi1qXi6N_country-{country_code.upper()}"
    host = "core-residential.evomi.com"
    port = 1000

    return {
        "username": username,
        "password": password,
        "host": host,
        "port": port,
        "server": f"http://{host}:{port}",
    }
