# main.py
from fastapi import FastAPI
from routers.products import router as products_router
from database import create_database

# NEW — LOAD .ENV
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="Gamestore API")

create_database()

app.include_router(products_router)

@app.get("/")
def root():
    return {"message": "Gamestore API running"}
