from pydantic import BaseModel
from typing import Optional, Generic, TypeVar

T = TypeVar("T")


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


class ApiSuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: Optional[str] = None


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: dict
