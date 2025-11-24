from pydantic import BaseModel, Field
from typing import Optional, Any

class AnalyzeProductRequest(BaseModel):
    url: str
    countryCode: str
    userAgent: str
    acceptLanguage: str
    locale: str
    timezoneId: str

class ProductData(BaseModel):
    title: Optional[str] = None
    price_value: Optional[str] = None
    currency: Optional[str] = None
    imageUrl: Optional[str] = None

class Validation(BaseModel):
    isDetailPage: bool
    reason: str

class ProductAnalysisResult(BaseModel):
    validation: Validation
    productData: Optional[ProductData] = None

class AnalyzeProductResponse(BaseModel):
    data: ProductAnalysisResult
    message: str
