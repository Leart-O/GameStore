# routers/products.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from models.product import Product, ProductCreate
from database import get_db_connection
from routers.api_key import get_api_key
from datetime import datetime
import sqlite3

router = APIRouter(prefix="/products", tags=["products"])

def row_to_product(row: sqlite3.Row) -> Product:
    return Product(**dict(row))

@router.get("/", response_model=List[Product])
def list_products(q: Optional[str] = Query(None),
                  brand: Optional[str] = Query(None),
                  status: Optional[str] = Query(None),
                  price_min: Optional[float] = Query(None),
                  price_max: Optional[float] = Query(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    if q:
        sql += " AND name LIKE ?"
        params.append(f"%{q}%")
    if brand:
        sql += " AND brand = ?"
        params.append(brand)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if price_min is not None:
        sql += " AND price >= ?"
        params.append(price_min)
    if price_max is not None:
        sql += " AND price <= ?"
        params.append(price_max)
    sql += " ORDER BY id DESC"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [row_to_product(r) for r in rows]

@router.get("/{product_id}", response_model=Product)
def get_product(product_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return row_to_product(row)

@router.post("/", response_model=Product, dependencies=[Depends(get_api_key)])
def create_product(product: ProductCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO products (name, brand, status, price, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (product.name, product.brand, product.status, product.price, now))
    conn.commit()
    product_id = cursor.lastrowid
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row_to_product(row)

@router.put("/{product_id}", response_model=Product, dependencies=[Depends(get_api_key)])
def update_product(product_id: int, product: ProductCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM products WHERE id = ?", (product_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
    cursor.execute("""
        UPDATE products
        SET name=?, brand=?, status=?, price=?
        WHERE id=?
    """, (product.name, product.brand, product.status, product.price, product_id))
    conn.commit()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row_to_product(row)

@router.delete("/{product_id}", status_code=204, dependencies=[Depends(get_api_key)])
def delete_product(product_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return
