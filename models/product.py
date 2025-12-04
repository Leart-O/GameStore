# models/product.py
from pydantic import BaseModel
from typing import Optional

class ProductBase(BaseModel):
    name: str
    brand: Optional[str] = None
    status: Optional[str] = None   # e.g. "in stock", "out of stock"
    price: Optional[float] = None

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int
    created_at: Optional[str] = None

    class Config:
        orm_mode = True
