import os
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from schemas import AnalyzeProductRequest
from services import analyze_and_extract_product_data
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'], allow_credentials=True,
    allow_methods=['*'], allow_headers=['*']
)

@app.post("/api/analyze-and-extract-product-data")
def analyze_and_extract_product_data_endpoint(request: AnalyzeProductRequest):
    try:
        result = analyze_and_extract_product_data(request)
        return {
            "data": result,
            "message": "Product analysis completed successfully"
        }
    except Exception as e:
        detail = f"Failed to analyze product: {str(e)}"
        tb = traceback.format_exc()
        logger.error(f"HTTP 500 Error: {str(e)}\n{tb}")
        raise HTTPException(status_code=500, detail=f"{detail}\nTRACE:\n{tb}")
