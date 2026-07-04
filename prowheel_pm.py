import streamlit as st
import pandas as pd
from datetime import datetime
from pyairtable import Api

# --- 1. GLOBAL SYSTEM CONFIGURATIONS ---
st.set_page_config(
    page_title="Wheelbuilder Lab", 
    layout="wide", 
    page_icon="🚲",
    initial_sidebar_state="collapsed" # Forces sidebar closed by default
)

# Completely hides the sidebar navigation drawer and its toggle button from clients
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True
)

GOOGLE_REVIEW_URL = "https://g.page/r/CVj8dcB7IKHrEAE/review"

# --- 2. AIRTABLE CONNECTION ---
try:
    API_KEY = st.secrets["airtable"]["api_key"]
    BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(API_KEY)
    base = api.base(BASE_ID)
except Exception:
    st.error("❌ Airtable Connection Error: Check your Streamlit Secrets.")
    st.stop()

# --- 3. CLIENT PORTAL RENDER ENGINE ---
def render_client_portal(target_build_id):
    try:
        with st.spinner("Loading secure build profile..."):
            record = base.table("builds").get(target_build_id)
            row = record.get("fields", {})
            row["id"] = record.get("id")
    except Exception:
        st.error("❌ Invalid or expired build link reference.")
        st.stop()

    st.markdown("<h1 style='text-align: center; margin-top:20px;'>🚲 WHEELBUILDER LAB</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Secure Client Verification Portal</p>", unsafe_allow_html=True)
    st.divider()

    auth_session_key = f"auth_{target_build_id}"
    if auth_session_key not in st.session_state:
        st.session_state[auth_session_key] = False

    if not st.session_state[auth_session_key]:
        correct_password = row.get("wp_page_password")
        if isinstance(correct_password, float) or not correct_password or str(correct_password).lower() in ["none", "nan"]:
            st.warning("This build sheet has not been assigned a secure access key yet. Please contact the workshop.")
            st.stop()

        c_pass, _ = st.columns([2, 3])
        with c_pass:
            user_input = st.text_input("🔑 Enter your Build Passkey:", type="password")
            
        if not user_input:
            st.info("Please enter the passkey sent to you to unlock your custom build metrics.")
            st.stop()
            
        if user_input.strip() != str(correct_password).strip():
            st.error("❌ Incorrect passkey. Please double-check your records.")
            st.stop()
            
        st.session_state[auth_session_key] = True
        st.rerun()

    f_weight_snapshot = int(row.get("f_weight", 0))
    r_weight_snapshot = int(row.get("r_weight", 0))
    
    f_exists = bool(row.get('f_rim')) and row.get('f_rim') != "None" and f_weight_snapshot > 0
    r_exists = bool(row.get('r_rim')) and row.get('r_rim') != "None" and r_weight_snapshot > 0

    st.markdown(f"## Your Custom Wheelset Build Sheet")
    st.markdown(f"**Client Profile:** {row.get('customer')} | **Completion Date:** {row.get('date')}")
    st.write("Thank you for choosing Wheelbuilder for your custom wheel build! Your wheelset is complete and ready for the road. Below you will find the verified specs, weights, invoice and logistics tracking information.")
    
    st.success("✨ **Warranty Record:** Your wheels come with a lifetime warranty on the workmanship and spokes. If you ever need any support or advice, please get in touch directly.")

    c_front, c_rear = st.columns(2)
    with c_front:
        if f_exists:
            st.markdown("### 🔘 Front Wheel Configuration")
            st.markdown(f"- **Rim:** {row.get('f_rim')}")
            st.markdown(f"- **Hub:** {row.get('f_hub')}")
            st.markdown(f"- **Spokes:** {row.get('spoke')} `Left: {row.get('f_l')}mm / Right: {row.get('f_r')}mm`")
            st.markdown(f"- **Nipples:** {row.get('nipple')}")
            st.metric("Verified Front Weight", f"{f_weight_snapshot}g")
            
    with c_rear:
        if r_exists:
            st.markdown("### 🔘 Rear Wheel Configuration")
            st.markdown(f"- **Rim:** {row.get('r_rim')}")
            st.markdown(f"- **Hub:** {row.get('r_hub')}")
            st.markdown(f"- **Spokes:** {row.get('spoke')} `Left: {row.get('r_l')}mm / Right: {row.get('r_r')}mm`")
            st.markdown(f"- **Nipples:** {row.get('nipple')}")
            st.metric("Verified Rear Weight", f"{r_weight_snapshot}g")

    st.divider()
    st.metric("📦 COMPLETE SYSTEM WHEELSET WEIGHT", f"{f_weight_snapshot + r_weight_snapshot}g")
    st.divider()

    c_btn1, c_btn2, c_btn3, c_btn4 = st.columns([1, 1, 1, 1])
    inv_url = str(row.get('invoice_url', '')).strip()
    track_url = str(row.get('tracking_link', '')).strip()
    gallery_url = str(row.get('gallery_url', '')).strip()

    with c_btn1:
        if inv_url and inv_url.lower() not in ['none', 'nan', '']:
            st.link_button("📄 Open Digital Invoice", inv_url, use_container_width=True)
    with c_btn2:
        if track_url and track_url.lower() not in ['none', 'nan', '']:
            st.link_button("🚚 Track Courier Shipment", track_url, use_container_width=True)
    with c_btn3:
        if gallery_url and gallery_url.lower() not in ['none', 'nan', '']:
            st.link_button("📸 View Build Gallery", gallery_url, use_container_width=True)
    with c_btn4:
        st.link_button("⭐️ Leave a Google Review", GOOGLE_REVIEW_URL, use_container_width=True)

    st.caption("🔒 Secured Archival Record. Property of Wheelbuilder Lab.")
    st.stop()

# --- 4. URL ROUTING DISPATCHER ---
if "build" in st.query_params:
    render_client_portal(st.query_params["build"])
else:
    # Fallback Landing Page if no query parameters are provided
    st.markdown("<h2 style='margin-top:40px;'>🚲 Wheelbuilder Lab</h2>", unsafe_allow_html=True)
    st.write("Welcome to the digital build sheet portal. If you are a customer looking for your verified wheel specifications, please use the unique link provided to you by your builder.")
    st.divider()
    
    # Discreet, secure programmatic navigation gateway to your admin page
    c_gate, _ = st.columns([2, 3])
    with c_gate:
        st.page_link("pages/Admin_Pipeline.py", label="🔒 Staff Console Login", icon="⚙️", use_container_width=True)
