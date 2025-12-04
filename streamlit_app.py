# streamlit_app.py
import streamlit as st
import requests
import os

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
PROD_API = f"{BASE_URL.rstrip('/')}/products/"

st.set_page_config(page_title="Gamestore", layout="wide")
st.title("Gamestore — Browse tech products (demo)")

with st.form("filters"):
    q = st.text_input("Search product name")
    brand = st.text_input("Brand (optional)")
    status = st.selectbox("Status", options=["", "in stock", "out of stock", "preorder"])
    col1, col2 = st.columns(2)
    with col1:
        price_min = st.number_input("Min price", value=0.0, step=1.0)
    with col2:
        price_max = st.number_input("Max price", value=10000.0, step=1.0)
    submitted = st.form_submit_button("Search")

params = {}
if q:
    params["q"] = q
if brand:
    params["brand"] = brand
if status:
    params["status"] = status
if price_min:
    params["price_min"] = price_min
if price_max:
    params["price_max"] = price_max

try:
    r = requests.get(PROD_API, params=params, timeout=10)
    r.raise_for_status()
    products = r.json()
except Exception as e:
    st.error("Could not fetch products from backend: " + str(e))
    products = []

st.write(f"Found {len(products)} products")

if "cart" not in st.session_state:
    st.session_state.cart = {}

cols = st.columns(3)
for i, p in enumerate(products):
    c = cols[i % 3]
    with c:
        st.subheader(p.get("name"))
        st.write("Brand:", p.get("brand") or "-")
        st.write("Price:", p.get("price") if p.get("price") is not None else "-")
        st.write("Status:", p.get("status") or "-")
        if st.button("View / Add to cart", key=f"view_{p['id']}"):
            st.session_state.selected = p

if st.session_state.get("selected"):
    item = st.session_state.selected
    st.sidebar.header("Selected product")
    st.sidebar.write(item.get("name"))
    st.sidebar.write("Brand:", item.get("brand"))
    st.sidebar.write("Price:", item.get("price"))
    qty = st.sidebar.number_input("Quantity", min_value=1, value=1)
    if st.sidebar.button("Add to cart"):
        cid = str(item["id"])
        cart = st.session_state.cart
        entry = cart.get(cid, {"product": item, "qty": 0})
        entry["qty"] += qty
        cart[cid] = entry
        st.sidebar.success("Added to cart")

st.sidebar.header("Cart")
total = 0.0
for cid, entry in st.session_state.cart.items():
    p = entry["product"]
    qty = entry["qty"]
    price = p.get("price") or 0
    st.sidebar.write(f"{p['name']} x{qty} — {price*qty}")
    total += price * qty
st.sidebar.write("Total:", total)
if st.sidebar.button("Clear cart"):
    st.session_state.cart = {}
