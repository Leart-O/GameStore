# streamlit_app.py
import streamlit as st
import requests
import os
from dotenv import load_dotenv
import json
from html import escape

# Load .env (if present)
load_dotenv()

# Config
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
PROD_API = f"{BASE_URL.rstrip('/')}/products/"

st.set_page_config(page_title="Gamestore", layout="wide")
st.title("Gamastore — Browse & Add Products")

# ---------------- Session-state triggers for modals ----------------
if "edit_product" not in st.session_state:
    st.session_state.edit_product = None
if "delete_product" not in st.session_state:
    st.session_state.delete_product = None

# --- Admin: API key handling ---
st.sidebar.header("API Key / Settings")

# Prefer API_KEYS environment entry; allow manual override in UI
env_api_keys = os.getenv("API_KEYS", "")
default_key = ""
if env_api_keys:
    # if multiple in CSV, pick first
    default_key = env_api_keys.split(",")[0].strip()

api_key_input = st.sidebar.text_input("API key (for POST/PUT/DELETE)", value=default_key, type="password")
save_key = st.sidebar.checkbox("Save API key to .env (project root)")

if save_key and api_key_input:
    env_path = os.path.join(os.getcwd(), ".env")
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("API_KEYS="):
                new_lines.append(f"API_KEYS={api_key_input}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"API_KEYS={api_key_input}")
        with open(env_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(new_lines))
        st.sidebar.success(".env updated (API_KEYS). Restart uvicorn if backend was running.")
    except Exception as e:
        st.sidebar.error(f"Could not write .env: {e}")

# Use the UI-provided key (if any) else default env key
API_KEY = api_key_input or default_key or None

# --- Add product form in the SIDEBAR as a dropdown (expander) ---
with st.sidebar.expander("➕ Add a new product", expanded=False):
    st.write("Create a new product and save it to the backend database.")
    with st.form("add_product_form"):
        name = st.text_input("Product name")
        brand_field = st.text_input("Brand (optional)")
        price_field = st.text_input("Price (numeric, e.g. 59.99)")
        status_field = st.selectbox("Status", options=["", "in stock", "out of stock", "preorder"])
        submit_add = st.form_submit_button("Add product (sidebar)")

    if submit_add:
        if not name:
            st.error("Product name is required.")
        else:
            try:
                price_val = float(price_field) if price_field not in ("", None) and price_field != "" else None
            except Exception:
                st.error("Price must be a number (e.g. 59.99).")
                price_val = None

            payload = {
                "name": name,
                "brand": brand_field or None,
                "status": status_field or None,
                "price": price_val
            }

            if not API_KEY:
                st.error("No API key available. Provide an API key in the sidebar (or set API_KEYS in .env).")
            else:
                headers = {"api-key": API_KEY, "Content-Type": "application/json"}
                try:
                    resp = requests.post(PROD_API, json=payload, headers=headers, timeout=10)
                    if resp.status_code in (200, 201):
                        st.success(f"Product created: {name}")
                        st.experimental_rerun()
                    else:
                        try:
                            detail = resp.json()
                        except Exception:
                            detail = resp.text
                        st.error(f"Backend error {resp.status_code}: {detail}")
                except Exception as e:
                    st.error("Failed to POST product: " + str(e))

# ---------------- Helper functions ----------------

def fetch_products(params=None):
    try:
        r = requests.get(PROD_API, params=params or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error("Could not fetch products from backend: " + str(e))
        return []

# ---------------- Filters form (existing UI) ----------------
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

# ---------------- Fetch products ----------------
products = fetch_products(params)
st.write(f"Found {len(products)} products")

# ---------------- Display products (grid) with uniform card height ----------------
if "cart" not in st.session_state:
    st.session_state.cart = {}

cols = st.columns(3)
card_fixed_height_px = 140  # adjust if needed

for i, p in enumerate(products):
    c = cols[i % 3]
    with c:
        name_html = escape(str(p.get("name") or ""))
        brand_html = escape(str(p.get("brand") or "-"))
        status_html = escape(str(p.get("status") or "-"))
        price_val = p.get("price")
        price_html = f"{price_val}" if price_val is not None else "-"

        card_html = f"""
        <div style="height:{card_fixed_height_px}px; padding:6px 8px; border-radius:8px;">
          <div style="font-weight:600; font-size:16px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{name_html}</div>
          <div style="margin-top:6px; font-size:13px; color:#333;">Brand: {brand_html}</div>
          <div style="font-size:13px; color:#333;">Price: {price_html}</div>
          <div style="font-size:13px; color:#333;">Status: {status_html}</div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

        # Buttons -> set session_state markers (so modal opens reliably after rerun)
        col_a, col_b, col_c = st.columns([1,1,1])
        with col_a:
            if st.button("Add to cart", key=f"view_{p.get('id')}"):
                st.session_state.selected = p
        with col_b:
            if st.button("✏️", key=f"edit_{p.get('id')}"):
                st.session_state.edit_product = p
                st.session_state.delete_product = None
                st.experimental_rerun()
        with col_c:
            if st.button("🗑️", key=f"delete_{p.get('id')}"):
                st.session_state.delete_product = p
                st.session_state.edit_product = None
                st.experimental_rerun()

# ---------------- Modals / forms triggered by session_state ----------------

# EDIT modal (uses modal if available, else sidebar expander fallback)
if st.session_state.edit_product:
    product = st.session_state.edit_product
    prod_id = product.get("id")
    try:
        with st.modal(f"Edit product — {product.get('name', '')}"):
            with st.form(f"edit_form_modal_{prod_id}"):
                e_name = st.text_input("Name", value=product.get("name") or "")
                e_brand = st.text_input("Brand", value=product.get("brand") or "")
                e_price = st.text_input("Price", value=str(product.get("price")) if product.get("price") is not None else "")
                e_status = st.selectbox("Status", options=["", "in stock", "out of stock", "preorder"],
                                        index=0 if not product.get("status") else (["","in stock","out of stock","preorder"].index(product.get("status")) if product.get("status") in ["in stock","out of stock","preorder"] else 0))
                submitted = st.form_submit_button("Save changes")
            if submitted:
                try:
                    price_val = float(e_price) if e_price not in ("", None) and e_price != "" else None
                except Exception:
                    st.error("Price must be numeric.")
                    st.session_state.edit_product = None
                    st.experimental_rerun()
                payload = {"name": e_name, "brand": e_brand or None, "status": e_status or None, "price": price_val}
                if not API_KEY:
                    st.error("Missing API key in sidebar.")
                else:
                    headers = {"api-key": API_KEY, "Content-Type": "application/json"}
                    try:
                        r = requests.put(f"{PROD_API}{prod_id}", json=payload, headers=headers, timeout=10)
                        if r.status_code in (200, 201):
                            st.success("Product updated.")
                            st.session_state.edit_product = None
                            st.experimental_rerun()
                        else:
                            try:
                                detail = r.json()
                            except Exception:
                                detail = r.text
                            st.error(f"Failed to update: {r.status_code} {detail}")
                            st.session_state.edit_product = None
                            st.experimental_rerun()
                    except Exception as e:
                        st.error("Network error during update: " + str(e))
                        st.session_state.edit_product = None
                        st.experimental_rerun()
    except AttributeError:
        # fallback: sidebar expander
        with st.sidebar.expander(f"Edit product — {product.get('name')}", expanded=True):
            with st.form(f"edit_form_sb_{prod_id}"):
                e_name = st.text_input("Name", value=product.get("name") or "", key=f"e_name_{prod_id}")
                e_brand = st.text_input("Brand", value=product.get("brand") or "", key=f"e_brand_{prod_id}")
                e_price = st.text_input("Price", value=str(product.get("price")) if product.get("price") is not None else "", key=f"e_price_{prod_id}")
                e_status = st.selectbox("Status", options=["", "in stock", "out of stock", "preorder"],
                                        index=0 if not product.get("status") else (["","in stock","out of stock","preorder"].index(product.get("status")) if product.get("status") in ["in stock","out of stock","preorder"] else 0),
                                        key=f"e_status_{prod_id}")
                submitted = st.form_submit_button("Save changes (sidebar)")
            if submitted:
                try:
                    price_val = float(e_price) if e_price not in ("", None) and e_price != "" else None
                except Exception:
                    st.error("Price must be numeric.")
                    st.session_state.edit_product = None
                    st.experimental_rerun()
                payload = {"name": e_name, "brand": e_brand or None, "status": e_status or None, "price": price_val}
                if not API_KEY:
                    st.error("Missing API key in sidebar.")
                else:
                    headers = {"api-key": API_KEY, "Content-Type": "application/json"}
                    try:
                        r = requests.put(f"{PROD_API}{prod_id}", json=payload, headers=headers, timeout=10)
                        if r.status_code in (200, 201):
                            st.success("Product updated.")
                            st.session_state.edit_product = None
                            st.experimental_rerun()
                        else:
                            try:
                                detail = r.json()
                            except Exception:
                                detail = r.text
                            st.error(f"Failed to update: {r.status_code} {detail}")
                            st.session_state.edit_product = None
                            st.experimental_rerun()
                    except Exception as e:
                        st.error("Network error during update: " + str(e))
                        st.session_state.edit_product = None
                        st.experimental_rerun()

# DELETE modal (similar pattern)
if st.session_state.delete_product:
    product = st.session_state.delete_product
    prod_id = product.get("id")
    try:
        with st.modal(f"Delete product — {product.get('name', '')}"):
            st.warning(f"Are you sure you want to permanently delete: \"{product.get('name')}\" ?")
            col1, col2 = st.columns([1, 3])
            with col1:
                confirm = st.button("Confirm delete", key=f"confirm_delete_modal_{prod_id}")
            with col2:
                cancel = st.button("Cancel", key=f"cancel_delete_modal_{prod_id}")
            if confirm:
                if not API_KEY:
                    st.error("Missing API key in sidebar.")
                else:
                    headers = {"api-key": API_KEY}
                    try:
                        r = requests.delete(f"{PROD_API}{prod_id}", headers=headers, timeout=10)
                        if r.status_code in (200, 204):
                            st.success("Product deleted.")
                            st.session_state.delete_product = None
                            st.experimental_rerun()
                        else:
                            try:
                                detail = r.json()
                            except Exception:
                                detail = r.text
                            st.error(f"Failed to delete: {r.status_code} {detail}")
                            st.session_state.delete_product = None
                            st.experimental_rerun()
                    except Exception as e:
                        st.error("Network error during delete: " + str(e))
                        st.session_state.delete_product = None
                        st.experimental_rerun()
            if cancel:
                st.session_state.delete_product = None
                st.experimental_rerun()
    except AttributeError:
        # fallback: sidebar confirm area
        with st.sidebar.expander(f"Delete product — {product.get('name')}", expanded=True):
            st.write(f"Are you sure you want to delete: **{product.get('name')}** ?")
            if st.button("Confirm delete (sidebar)", key=f"confirm_delete_sb_{prod_id}"):
                if not API_KEY:
                    st.error("Missing API key in sidebar.")
                else:
                    headers = {"api-key": API_KEY}
                    try:
                        r = requests.delete(f"{PROD_API}{prod_id}", headers=headers, timeout=10)
                        if r.status_code in (200, 204):
                            st.success("Product deleted.")
                            st.session_state.delete_product = None
                            st.experimental_rerun()
                        else:
                            try:
                                detail = r.json()
                            except Exception:
                                detail = r.text
                            st.error(f"Failed to delete: {r.status_code} {detail}")
                            st.session_state.delete_product = None
                            st.experimental_rerun()
                    except Exception as e:
                        st.error("Network error during delete: " + str(e))
                        st.session_state.delete_product = None
                        st.experimental_rerun()

# ---------------- Sidebar selected product & cart ----------------
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

# End of file
