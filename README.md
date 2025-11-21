# Eyra Scraper (FastAPI + Playwright Stealth)

This is a FastAPI backend for robust, bot-proof product scraping and AgentQL-powered page analysis.

---

## Features
- Full stealth browsing with Python Playwright + [playwright-stealth](https://github.com/AtuboDad/playwright_stealth)
- `/api/analyze-and-extract-product-data` POST endpoint for product page analysis (request/response schema matches previous Node/Express app)
- Proxy, user-agent, and anti-bot customization ready
- AgentQL API support for robust data extraction from arbitrary pages

---

## Setup & Installation
1. **Clone this repo** (if you haven't)
2. **Create a virtual environment**:
    ```bash
    python -m venv venv
    # On Windows:
    venv\Scripts\activate
    # On Mac/Linux:
    source venv/bin/activate
    ```
3. **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    python -m playwright install
    ```
4. **Configure environment**:
    - Copy `.env.example` to `.env` and set your `AGENTQL_API_KEY`.
5. **Run the server**:
    ```bash
    uvicorn main:app --reload
    ```
    The server will listen at `http://localhost:8000`.

---

## API Usage
- **POST** `/api/analyze-and-extract-product-data`
    - **Request JSON** (example):
      ```json
      {
        "url": "https://example.com/product/123",
        "cookies": null,
        "countryCode": "US",
        "userAgent": "Your-UA-string-here",
        "locale": "en-US",
        "timezoneId": "America/New_York",
        "geolocation": null,
        "acceptLanguage": "en-US,en"
      }
      ```
    - **Response JSON**:
      ```json
      {
        "data": {
          "validation": {
            "isDetailPage": true,
            "reason": "Clear single product with main details present."
          },
          "productData": {
            "title": "Widget Pro",
            "price_value": "99.99",
            "currency": "USD",
            "imageUrl": "https://example.com/widget.jpg"
          }
        },
        "message": "Product analysis completed successfully"
      }
      ```

---

## Environment Variables
- `AGENTQL_API_KEY` — your AgentQL private API key

---

## Tech Stack
- Python 3.9+
- FastAPI
- Playwright (with [playwright-stealth](https://github.com/AtuboDad/playwright_stealth))
- httpx
- Pydantic
- dotenv

---

## Credits
- Playwright Stealth adapted from [playwright_stealth](https://github.com/AtuboDad/playwright_stealth)
- API structure inspired by previous Express TypeScript project and [AgentQL](https://agentql.com/)
