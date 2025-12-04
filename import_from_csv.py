# import_from_csv.py
import csv
import os
import requests
from database import get_db_connection, create_database
from urllib.parse import urljoin

"""
Usage examples:
1) Direct DB insert:
   python import_from_csv.py --file octoparse.csv --mode db

2) POST to running API:
   python import_from_csv.py --file octoparse.csv --mode api --api-key yourkey
"""

import argparse

def parse_row(row):
    name = row.get("name") or row.get("Name") or row.get("product") or ""
    brand = row.get("brand") or row.get("Brand") or ""
    status = row.get("status") or row.get("Status") or ""
    price_raw = row.get("price") or row.get("Price") or "0"
    try:
        p = price_raw.replace("€","").replace("$","").replace(",","").strip()
        pnum = float(''.join(ch for ch in p if ch.isdigit() or ch == "." or ch == "-") or 0)
    except Exception:
        pnum = 0.0
    return {"name": name.strip(), "brand": brand.strip(), "status": status.strip(), "price": pnum}

def insert_direct(csv_path):
    create_database()
    conn = get_db_connection()
    cursor = conn.cursor()
    with open(csv_path, newline='', encoding='utf-8') as fh:
        dr = csv.DictReader(fh)
        rows = []
        for r in dr:
            obj = parse_row(r)
            if not obj["name"]:
                continue
            rows.append((obj["name"], obj["brand"], obj["status"], obj["price"]))
        cursor.executemany("""
            INSERT INTO products (name, brand, status, price, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, [(n,b,s,p) for (n,b,s,p) in rows])
        conn.commit()
        print(f"Inserted {len(rows)} rows into DB.")
    conn.close()

def post_to_api(csv_path, base_url, api_key):
    endpoint = urljoin(base_url, "products/")
    headers = {"Content-Type":"application/json", "api-key": api_key}
    import json
    count = 0
    with open(csv_path, newline='', encoding='utf-8') as fh:
        dr = csv.DictReader(fh)
        for r in dr:
            obj = parse_row(r)
            if not obj["name"]:
                continue
            payload = {
                "name": obj["name"],
                "brand": obj["brand"],
                "status": obj["status"],
                "price": obj["price"]
            }
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            if resp.status_code in (200,201):
                count += 1
            else:
                print("Failed:", resp.status_code, resp.text, "payload:", payload)
    print(f"Posted {count} products to API.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", "-f", required=True, help="CSV file from Octoparse")
    parser.add_argument("--mode", choices=("db","api"), default="db", help="db = write sqlite directly, api = POST to running API")
    parser.add_argument("--api-key", default=os.getenv("API_KEYS"), help="API key (for api mode)")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL","http://127.0.0.1:8000"), help="API base url")
    args = parser.parse_args()

    if args.mode == "db":
        insert_direct(args.file)
    else:
        if not args.api_key:
            print("API key required for api mode. Provide --api-key or set API_KEYS in .env")
            return
        post_to_api(args.file, args.base_url, args.api_key)

if __name__ == "__main__":
    main()
