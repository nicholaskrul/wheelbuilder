import streamlit as st
import pandas as pd
import time
import secrets
import string
import math
import urllib.parse
from datetime import datetime, timedelta
from pyairtable import Api

# =========================================================================
# --- 1. GLOBAL WORKSHOP CONFIGURATIONS (YOUR CONTROL PANEL) ---
# =========================================================================
st.set_page_config(page_title="Wheelbuilder Lab Command Center", layout="wide", page_icon="🚲")

LIVE_DOMAIN = "https://wheelbuilder.streamlit.app" if "localhost" not in st.secrets.get("airtable", {}).get("base_id", "") else "http://localhost:8501"
GOOGLE_REVIEW_URL = "https://g.page/r/CVj8dcB7IKHrEAE/review"
CACHE_DATA_TTL = 86400  # 24-hour cache TTL to minimize read requests on GitHub / Streamlit Cloud
WORKSHOP_CAPTION = "Workshop Command Center | Low-API Quota Engine Active"

STATUS_STAGES = ["Order Received", "Parts Received", "Building", "Complete"]
STOCK_ORDER_STAGES = ["Ordered", "Shipped", "Delivered", "Cancelled"]

# =========================================================================
# --- 2. AIRTABLE CONNECTION ENGINE ---
# =========================================================================
try:
    API_KEY = st.secrets["airtable"]["api_key"]
    BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(API_KEY)
    base = api.base(BASE_ID)
except Exception:
    st.error("❌ Airtable Connection Error: Check your Streamlit Secrets.")
    st.stop()

# =========================================================================
# --- 3. CORE ANALYTICS & DEFENSIVE PROGRAMMING HELPERS ---
# =========================================================================
def safe_float(val, default=0.0):
    """Defensive Engine: Prevents application crashes from bad alphanumeric entries and NaNs."""
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
        
    val_str = str(val).lower().strip()
    if val_str in ["nan", "none", "null", ""]:
        return default
        
    try:
        return float(val)
    except (ValueError, TypeError):
        clean_str = ''.join(c for c in val_str if c.isdigit() or c == '.')
        try:
            return float(clean_str) if clean_str else default
        except ValueError:
            return default

def safe_int(val, default=0):
    """Defensive Engine: Securely parses integers, intercepting NaNs and None values."""
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
        
    val_str = str(val).lower().strip()
    if val_str in ["nan", "none", "null", ""]:
        return default
        
    try:
        return int(float(val))
    except (ValueError, TypeError):
        clean_str = ''.join(c for c in val_str if c.isdigit())
        try:
            return int(clean_str) if clean_str else default
        except ValueError:
            return default

def safe_airtable_update(table_name, record_id, updates):
    """Safely updates Airtable records with typecasting enabled to prevent Single Select / Date field errors."""
    try:
        base.table(table_name).update(record_id, updates, typecast=True)
        return True, "Updated successfully!"
    except Exception as e:
        err_msg = str(e)
        if "UNKNOWN_FIELD_NAME" in err_msg or "422" in err_msg:
            return False, f"❌ Airtable Error: Please ensure columns exist in your Airtable base! Details: {err_msg}"
        return False, f"❌ Update Failed: {err_msg}"

def get_comp_data_from_bundle(bundle, table_key, label):
    if not label or str(label).lower().strip() in ["none", "nan", ""]: 
        return {}
    df = bundle.get(table_key, pd.DataFrame())
    if df.empty or 'label' not in df.columns: 
        return {}
    target = str(label).lower().strip()
    match = df[df['label'].astype(str).str.strip().str.lower() == target]
    if not match.empty:
        return match.iloc[0].to_dict()
    return {}

def calculate_wheel_weights(row, bundle):
    """Calculates weights dynamically using defensive type-safe parsing engines."""
    spk_data = get_comp_data_from_bundle(bundle, "spokes", row.get('spoke'))
    nip_data = get_comp_data_from_bundle(bundle, "nipples", row.get('nipple'))
    
    u_spk = safe_float(spk_data.get('weight', 0))
    u_nip = safe_float(nip_data.get('weight', 0))

    f_res = {"total": 0.0, "exists": False}
    if row.get('f_rim') and str(row.get('f_rim')).lower().strip() != "none":
        frd = get_comp_data_from_bundle(bundle, "rims", row.get('f_rim'))
        fhd = get_comp_data_from_bundle(bundle, "hubs", row.get('f_hub'))
        h = int(safe_float(frd.get('holes', 0)))
        if h == 0:
            h = 28  # Fallback default spoke count if unspecified
        f_res.update({
            "exists": True, 
            "rim_w": safe_float(frd.get('weight', 0)), 
            "hub_w": safe_float(fhd.get('weight', 0))
        })
        f_res["total"] = f_res["rim_w"] + f_res["hub_w"] + (h * (u_spk + u_nip))

    r_res = {"total": 0.0, "exists": False}
    if row.get('r_rim') and str(row.get('r_rim')).lower().strip() != "none":
        rrd = get_comp_data_from_bundle(bundle, "rims", row.get('r_rim'))
        rhd = get_comp_data_from_bundle(bundle, "hubs", row.get('r_hub'))
        h = int(safe_float(rrd.get('holes', 0)))
        if h == 0:
            h = 28  # Fallback default spoke count if unspecified
        r_res.update({
            "exists": True, 
            "rim_w": safe_float(rrd.get('weight', 0)), 
            "hub_w": safe_float(rhd.get('weight', 0))
        })
        r_res["total"] = r_res["rim_w"] + r_res["hub_w"] + (h * (u_spk + u_nip))
        
    return f_res, r_res

def format_clean_phone(phone_str):
    """Cleans phone numbers for WhatsApp integration (e.g., 27821234567)."""
    if not phone_str: 
        return ""
    clean = "".join(c for c in str(phone_str) if c.isdigit())
    if clean.startswith("0"):
        clean = "27" + clean[1:]  # Default South Africa format
    return clean

def format_10digit_phone(phone_str):
    """Standardises phone numbers to a 10-digit format (e.g. 0821234567) for portal passwords."""
    if not phone_str: 
        return ""
    clean = "".join(c for c in str(phone_str) if c.isdigit())
    if clean.startswith("27") and len(clean) == 11:
        clean = "0" + clean[2:]
    elif len(clean) > 10 and clean.startswith("27"):
        clean = "0" + clean[2:]
    return clean

def generate_update_message(customer_name, status, portal_url, passkey):
    """Generates standard notification messages for clients."""
    status_emoji = {
        "Order Received": "📋",
        "Parts Received": "📦",
        "Building": "🛠️",
        "Complete": "🎉"
    }.get(status, "🚲")

    msg = (
        f"Hi {customer_name}! {status_emoji} Quick update from Wheelbuilder Lab:\n"
        f"Your custom build status is now: *{status}*\n\n"
        f"You can view live updates and specifications on your portal here:\n"
        f"🔗 {portal_url}\n"
        f"🔑 Password: Your 10-digit registered phone number ({passkey})\n\n"
        f"Let us know if you have any questions!"
    )
    return msg

@st.cache_data(ttl=CACHE_DATA_TTL, show_spinner="Syncing Workshop Data...")
def fetch_master_bundle():
    """Fetches full bundle from Airtable and caches in memory across user sessions."""
    tables = {
        "builds": "customer", 
        "rims": "rim", 
        "hubs": "hub", 
        "spokes": "spoke", 
        "nipples": "nipple", 
        "spoke_db": "combo_id",
        "stock_orders": "supplier"
    }
    bundle = {}
    for table_name, label_col in tables.items():
        try:
            records = base.table(table_name).all()
            if not records:
                bundle[table_name] = pd.DataFrame()
                continue
            data = []
            for rec in records:
                fields = rec['fields']
                fields['id'] = rec['id']
                if label_col in fields: 
                    fields['label'] = str(fields[label_col]).strip()
                data.append(fields)
            df = pd.DataFrame(data)
            for col in df.columns:
                # Fix IndexError on empty list fields returned from Airtable
                df[col] = df[col].apply(
                    lambda x: x[0] if (isinstance(x, list) and len(x) > 0) else (None if isinstance(x, list) else x)
                )
            bundle[table_name] = df
        except Exception:
            bundle[table_name] = pd.DataFrame()
    return bundle

# In-Memory Local Mutations (Deduplicates records to prevent inflated count analytics)
def update_local_record(table_name, record_id, updates):
    if 'data' not in st.session_state:
        st.session_state.data = fetch_master_bundle()
    df = st.session_state.data.get(table_name, pd.DataFrame())
    if not df.empty and record_id in df['id'].values:
        for key, val in updates.items():
            df.loc[df['id'] == record_id, key] = val
        st.session_state.data[table_name] = df

def add_local_record(table_name, record_dict):
    if 'data' not in st.session_state:
        st.session_state.data = fetch_master_bundle()
    df = st.session_state.data.get(table_name, pd.DataFrame())
    rec_id = record_dict.get('id')
    if not df.empty and rec_id and 'id' in df.columns:
        df = df[df['id'] != rec_id]
    new_df = pd.DataFrame([record_dict])
    if df.empty:
        st.session_state.data[table_name] = new_df
    else:
        st.session_state.data[table_name] = pd.concat([df, new_df], ignore_index=True)

def compute_workshop_analytics(bundle, completed_only=False):
    """Computes Workshop Trends analytics in-memory with strict deduplication."""
    df_builds = bundle.get("builds", pd.DataFrame())
    df_rims = bundle.get("rims", pd.DataFrame())
    
    if df_builds.empty:
        return {}

    # 1. Deduplicate by unique build record ID to prevent double-counting
    if 'id' in df_builds.columns:
        df_builds = df_builds.drop_duplicates(subset=['id'], keep='last')

    # 2. Filter by status scope if requested
    if completed_only and 'status' in df_builds.columns:
        df_builds = df_builds[df_builds['status'] == "Complete"]

    if df_builds.empty:
        return {}

    rim_holes_map = {}
    if not df_rims.empty and 'label' in df_rims.columns and 'holes' in df_rims.columns:
        for _, r_row in df_rims.iterrows():
            lbl = str(r_row.get('label', '')).strip().lower()
            if lbl:
                rim_holes_map[lbl] = int(safe_float(r_row.get('holes', 28)))

    all_rims = []
    all_hubs = []
    spoke_records = []
    nipple_records = []
    total_wheels = 0

    for _, row in df_builds.iterrows():
        b_date = str(row.get('date', '')).strip()
        # Parse Month cleanly without defaulting unpopulated dates to current month
        if b_date and b_date.lower() not in ["none", "nan", ""] and len(b_date) >= 7 and b_date[:4].isdigit():
            month_str = b_date[:7]
        else:
            month_str = "Unspecified Date"
        
        f_rim = str(row.get('f_rim', '')).strip()
        r_rim = str(row.get('r_rim', '')).strip()
        f_hub = str(row.get('f_hub', '')).strip()
        r_hub = str(row.get('r_hub', '')).strip()
        spk_model = str(row.get('spoke', '')).strip()
        nip_model = str(row.get('nipple', '')).strip()
        
        if not spk_model or spk_model.lower() == "none":
            spk_model = "Unspecified Spoke"
        if not nip_model or nip_model.lower() == "none":
            nip_model = "Unspecified Nipple"

        # Front Wheel
        if f_rim and f_rim.lower() != "none":
            total_wheels += 1
            all_rims.append(f_rim)
            if f_hub and f_hub.lower() != "none":
                all_hubs.append(f_hub)
            
            f_holes = rim_holes_map.get(f_rim.lower(), 28)
            if f_holes <= 0 or f_holes > 48:
                f_holes = 28
            
            spoke_records.append({"model": spk_model, "count": f_holes, "month": month_str})
            nipple_records.append({"model": nip_model, "count": f_holes, "month": month_str})

        # Rear Wheel
        if r_rim and r_rim.lower() != "none":
            total_wheels += 1
            all_rims.append(r_rim)
            if r_hub and r_hub.lower() != "none":
                all_hubs.append(r_hub)
            
            r_holes = rim_holes_map.get(r_rim.lower(), 28)
            if r_holes <= 0 or r_holes > 48:
                r_holes = 28
            
            spoke_records.append({"model": spk_model, "count": r_holes, "month": month_str})
            nipple_records.append({"model": nip_model, "count": r_holes, "month": month_str})

    df_spk = pd.DataFrame(spoke_records)
    df_nip = pd.DataFrame(nipple_records)

    top_rims = pd.Series(all_rims).value_counts().head(10) if all_rims else pd.Series(dtype=int)
    top_hubs = pd.Series(all_hubs).value_counts().head(10) if all_hubs else pd.Series(dtype=int)

    return {
        "df_builds_processed": df_builds,
        "rim_holes_map": rim_holes_map,
        "total_builds": len(df_builds),
        "total_wheels": total_wheels,
        "top_rims": top_rims,
        "top_hubs": top_hubs,
        "df_spk": df_spk,
        "df_nip": df_nip
    }

# =========================================================================
# --- 4. FUNCTIONAL PAGE MODULES ---
# =========================================================================

def render_client_portal():
    """Client View Module: Zero API Calls when reading from cached bundle."""
    # --- BLACK BRANDING THEME INJECTION ---
    st.markdown("""
        <style>
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
        }
        .stApp {
            background-color: #000000 !important;
            color: #FFFFFF !important;
        }
        h1, h2, h3, h4, h5, h6, p, label, span, div {
            color: #FFFFFF !important;
        }
        [data-testid="stMetricValue"] {
            color: #00FFCC !important;
        }
        [data-testid="stMetricLabel"] {
            color: #D0D0D0 !important;
        }
        .stTextInput input {
            background-color: #121212 !important;
            color: #FFFFFF !important;
            border: 1px solid #333333 !important;
        }
        hr {
            border-color: #222222 !important;
            margin: 1.5rem 0 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    target_build_id = st.query_params.get("build")
    if not target_build_id:
        st.error("❌ No build specified.")
        return

    # Use session state or cached bundle (0 API calls!)
    bundle = st.session_state.get('data', fetch_master_bundle())
    df_builds = bundle.get("builds", pd.DataFrame())

    row = {}
    if not df_builds.empty and target_build_id in df_builds['id'].values:
        row = df_builds[df_builds['id'] == target_build_id].iloc[0].to_dict()
    else:
        # Fallback to single record fetch if missing from memory
        try:
            record = base.table("builds").get(target_build_id)
            row = record.get("fields", {})
            row["id"] = record.get("id")
        except Exception:
            st.error("❌ Invalid or expired build link reference.")
            return

    # --- BRAND LOGO & HEADER ROW ---
    col_logo, col_title = st.columns([1, 4], vertical_alignment="center")
    with col_logo:
        try:
            st.image("WB_logo.png", width=170)
        except Exception:
            st.markdown("<h2 style='margin:0;'>🚲 WHEELBUILDER LAB</h2>", unsafe_allow_html=True)
    with col_title:
        st.markdown(
            "<span style='font-size: 1.45rem; color: #A0A0A0 !important; font-weight: 400; margin-left: 10px;'>"
            "Secure Self-Service Build Portal</span>", 
            unsafe_allow_html=True
        )

    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

    auth_session_key = f"auth_{target_build_id}"
    if auth_session_key not in st.session_state:
        st.session_state[auth_session_key] = False

    if not st.session_state[auth_session_key]:
        raw_pass = row.get("wp_page_password")
        raw_phone = row.get("phone", "")
        
        expected_pass = format_10digit_phone(raw_pass) if (raw_pass and str(raw_pass).lower() not in ["none", "nan", ""]) else format_10digit_phone(raw_phone)

        if not expected_pass:
            st.warning("This build sheet has not been assigned a registered 10-digit phone number yet.")
            return

        c_pass, _ = st.columns([2, 3])
        with c_pass:
            user_input = st.text_input("🔑 Enter your 10-Digit Registered Phone Number:", type="password", placeholder="e.g. 0821234567")
        if not user_input:
            st.info("Please enter your 10-digit registered phone number to unlock your custom build portal.")
            return
        
        clean_user_input = format_10digit_phone(user_input)
        if clean_user_input != expected_pass and user_input.strip() != str(raw_pass).strip():
            st.error("❌ Incorrect phone number.")
            return
            
        st.session_state[auth_session_key] = True
        st.rerun()

    current_status = row.get("status", "Order Received")
    
    # --- LIVE PROGRESS STEPPER ---
    st.markdown("### 📊 Live Build Progress")
    current_idx = STATUS_STAGES.index(current_status) if current_status in STATUS_STAGES else 0
    
    cols = st.columns(len(STATUS_STAGES))
    for idx, stage in enumerate(STATUS_STAGES):
        with cols[idx]:
            if idx < current_idx:
                st.success(f"✅ {stage}")
            elif idx == current_idx:
                st.info(f"⏳ **{stage}**")
            else:
                st.caption(f"⚪ {stage}")
                
    st.progress((current_idx + 1) / len(STATUS_STAGES))

    build_notes = str(row.get('notes', '')).strip()
    if build_notes and build_notes.lower() not in ["none", "nan", ""]:
        st.info(f"📢 **Workshop Update Note:** {build_notes}")

    st.divider()

    # --- DYNAMIC WEIGHT COMPUTATION ENGINE ---
    f_res, r_res = calculate_wheel_weights(row, bundle)

    f_weight_snap = safe_int(row.get("f_weight", 0))
    r_weight_snap = safe_int(row.get("r_weight", 0))

    f_weight_disp = f_weight_snap if f_weight_snap > 0 else safe_int(f_res["total"])
    r_weight_disp = r_weight_snap if r_weight_snap > 0 else safe_int(r_res["total"])

    f_exists = f_res["exists"] or (bool(row.get('f_rim')) and str(row.get('f_rim')).lower() != "none")
    r_exists = r_res["exists"] or (bool(row.get('r_rim')) and str(row.get('r_rim')).lower() != "none")

    st.markdown("## Custom Wheelset Build Sheet")
    st.markdown(f"**Client Profile:** {row.get('customer')} | **Registered:** {row.get('date')}")
    st.write("Welcome to your custom wheel build tracker! Component specs and weights update here dynamically.")
    st.success("✨ **Warranty Record:** Your wheels come with a lifetime warranty on workmanship and spokes.")

    c_front, c_rear = st.columns(2)
    with c_front:
        if f_exists:
            st.markdown("### 🔘 Front Wheel Configuration")
            st.markdown(f"- **Rim:** {row.get('f_rim')}")
            st.markdown(f"- **Hub:** {row.get('f_hub')}")
            st.markdown(f"- **Spokes:** {row.get('spoke')} `Left: {row.get('f_l')}mm / Right: {row.get('f_r')}mm`")
            st.markdown(f"- **Nipples:** {row.get('nipple')}")
            if f_weight_disp > 0:
                f_lbl = "Verified Front Weight" if f_weight_snap > 0 else "Estimated Front Weight"
                st.metric(f_lbl, f"{f_weight_disp}g")
    with c_rear:
        if r_exists:
            st.markdown("### 🔘 Rear Wheel Configuration")
            st.markdown(f"- **Rim:** {row.get('r_rim')}")
            st.markdown(f"- **Hub:** {row.get('r_hub')}")
            st.markdown(f"- **Spokes:** {row.get('spoke')} `Left: {row.get('r_l')}mm / Right: {row.get('r_r')}mm`")
            st.markdown(f"- **Nipples:** {row.get('nipple')}")
            if r_weight_disp > 0:
                r_lbl = "Verified Rear Weight" if r_weight_snap > 0 else "Estimated Rear Weight"
                st.metric(r_lbl, f"{r_weight_disp}g")

    total_system_weight = (f_weight_disp if f_exists else 0) + (r_weight_disp if r_exists else 0)
    if total_system_weight > 0:
        st.divider()
        sys_lbl = "📦 VERIFIED WHEELSET WEIGHT" if (f_weight_snap > 0 or r_weight_snap > 0) else "📦 ESTIMATED WHEELSET WEIGHT"
        st.metric(sys_lbl, f"{total_system_weight}g")
    
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


def render_admin_pipeline():
    """Administrative View Module: Low API Quota Builders Console."""
    if "admin_authenticated" not in st.session_state: 
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        st.markdown("<h2 style='margin-top:40px;'>🔓 Workshop Administration Panel</h2>", unsafe_allow_html=True)
        st.divider()
        c_login, _ = st.columns([2, 3])
        with c_login:
            user_entered_password = st.text_input("Enter Master Password:", type="password")
            if st.button("Unlock Workshop Console", use_container_width=True):
                admin_pass = st.secrets.get("admin", {}).get("password", "")
                if user_entered_password and user_entered_password == admin_pass:
                    st.session_state.admin_authenticated = True
                    st.toast("Authenticated!")
                    st.rerun()
                else: 
                    st.error("❌ Invalid Password.")
        return

    if 'data' not in st.session_state: 
        st.session_state.data = fetch_master_bundle()

    def refresh_api():
        st.cache_data.clear()
        st.session_state.data = fetch_master_bundle()

    st.title("🚲 Wheelbuilder Lab Command Center")
    st.caption(WORKSHOP_CAPTION)
    
    tabs = st.tabs(["🏁 Workshop", "🚚 Stock Orders", "📊 Trends", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

    # -------------------------------------------------------------------------
    # TAB 0: WORKSHOP PIPELINE
    # -------------------------------------------------------------------------
    with tabs[0]:
        c_head, c_sync, c_logout = st.columns([4, 1, 1])
        with c_head:
            st.subheader("🏁 Workshop Pipeline")
        with c_sync:
            if st.button("🔄 Force Sync", use_container_width=True, help="Only click if you made manual edits in Airtable web UI"):
                refresh_api()
                st.toast("Re-synced with Airtable!")
                st.rerun()
        with c_logout:
            if st.button("🔒 Lock Console", use_container_width=True):
                st.session_state.admin_authenticated = False
                st.rerun()

        df_builds = st.session_state.data["builds"]
        if df_builds.empty: 
            st.info("No active builds found.")
        else:
            active_mask = df_builds['status'].fillna("Order Received") != "Complete"
            active_builds = df_builds[active_mask].sort_values(by='customer', key=lambda col: col.str.lower())
            completed_builds = df_builds[~active_mask].sort_values(by='customer', key=lambda col: col.str.lower())

            st.write(f"### 🛠️ Active Builds ({len(active_builds)})")
            for _, row in active_builds.iterrows():
                f_res, r_res = calculate_wheel_weights(row, st.session_state.data)
                addr_val, track_val = row.get('delivery_address'), row.get('tracking_link')
                has_addr = isinstance(addr_val, str) and bool(addr_val.strip()) and addr_val.lower() not in ["none", "nan"]
                has_tracking = isinstance(track_val, str) and bool(track_val.strip()) and track_val.lower() not in ["none", "nan"]
                addr_flag = " 📮" if (has_addr or has_tracking) else ""

                with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')}{addr_flag}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown("**🔘 FRONT**")
                        if f_res["exists"]:
                            st.markdown(f"**{row.get('f_rim')}**")
                            st.caption(f"{row.get('f_hub')}")
                            st.info(f"📏 L: {row.get('f_l')} / R: {row.get('f_r')} mm")
                            st.metric("Est Weight", f"{safe_int(f_res['total'])}g")
                        else:
                            st.write("---")
                    with c2:
                        st.markdown("**🔘 REAR**")
                        if r_res["exists"]:
                            st.markdown(f"**{row.get('r_rim')}**")
                            st.caption(f"{row.get('r_hub')}")
                            st.success(f"📏 L: {row.get('r_l')} / R: {row.get('r_r')} mm")
                            st.metric("Est Weight", f"{safe_int(r_res['total'])}g")
                        else:
                            st.write("---")
                    with c3:
                        if f_res["exists"] or r_res["exists"]:
                            st.metric("📦 EST SET", f"{safe_int(f_res['total'] + r_res['total'])}g")
                        cur = row.get('status', 'Order Received')
                        new_s = st.selectbox(
                            "Status", 
                            STATUS_STAGES, 
                            index=STATUS_STAGES.index(cur) if cur in STATUS_STAGES else 0, 
                            key=f"s_{row['id']}"
                        )
                        
                        if new_s != cur:
                            updates = {"status": new_s}

                            wp_pass = row.get("wp_page_password")
                            if not wp_pass or str(wp_pass).lower() in ["none", "nan", ""]:
                                phone_10 = format_10digit_phone(row.get("phone", ""))
                                generated_pass = phone_10 if phone_10 else ("WS-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6)))
                                generated_url = f"{LIVE_DOMAIN}/?build={row['id']}"
                                updates.update({
                                    "wp_page_password": generated_pass,
                                    "wp_page_url": generated_url
                                })

                            if new_s == "Complete":
                                f_wt_snap = safe_int(f_res["total"]) if f_res["exists"] else 0
                                r_wt_snap = safe_int(r_res["total"]) if r_res["exists"] else 0
                                updates.update({
                                    "date": datetime.now().strftime("%Y-%m-%d"), 
                                    "f_weight": f_wt_snap, 
                                    "r_weight": r_wt_snap
                                })
                            
                            # 1 Update API Call + 0 Read API Calls (Mutate local memory)
                            success, msg = safe_airtable_update("builds", row['id'], updates)
                            if success:
                                update_local_record("builds", row['id'], updates)
                                st.toast(f"Status updated to {new_s}!")
                                st.rerun()
                            else:
                                st.error(msg)

                    phone = row.get("phone", "")
                    email = row.get("email", "")
                    portal_url = row.get("wp_page_url", f"{LIVE_DOMAIN}/?build={row['id']}")
                    passkey = format_10digit_phone(row.get("wp_page_password", "")) or format_10digit_phone(phone)

                    with st.popover("📲 Send Status Update to Client"):
                        st.markdown("#### Send Notification")
                        
                        if not passkey:
                            st.warning("⚠️ This build does not have a phone number or portal passkey assigned.")
                            if st.button("🔑 Set Phone Passkey Now", key=f"gen_key_{row['id']}", use_container_width=True):
                                phone_10 = format_10digit_phone(phone)
                                gen_pass = phone_10 if phone_10 else ("WS-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6)))
                                gen_url = f"{LIVE_DOMAIN}/?build={row['id']}"
                                updates = {"wp_page_password": gen_pass, "wp_page_url": gen_url}
                                
                                success, msg = safe_airtable_update("builds", row['id'], updates)
                                if success:
                                    update_local_record("builds", row['id'], updates)
                                    st.toast("Portal passkey synchronized!")
                                    st.rerun()
                                else:
                                    st.error(msg)
                        else:
                            msg_text = generate_update_message(row.get('customer'), row.get('status'), portal_url, passkey)
                            encoded_msg = urllib.parse.quote(msg_text)
                            st.code(msg_text, language="text")
                            
                            c_wa, c_em = st.columns(2)
                            with c_wa:
                                clean_p = format_clean_phone(phone)
                                wa_url = f"https://wa.me/{clean_p}?text={encoded_msg}" if clean_p else f"https://wa.me/?text={encoded_msg}"
                                st.link_button("📲 Send WhatsApp", wa_url, use_container_width=True)
                            with c_em:
                                subject = urllib.parse.quote(f"Wheelbuilder Lab Update: {row.get('status')}")
                                body = urllib.parse.quote(msg_text)
                                mailto_url = f"mailto:{email}?subject={subject}&body={body}"
                                st.link_button("✉️ Send Email", mailto_url, use_container_width=True)

                    c_btn1, c_btn2, c_btn3 = st.columns(3)
                    with c_btn1:
                        with st.popover("📝 Details"):
                            fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                            rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                            c_phone = st.text_input("Phone", value=row.get('phone', ''), key=f"ph_{row['id']}")
                            c_email = st.text_input("Email", value=row.get('email', ''), key=f"em_{row['id']}")
                            gal = st.text_input("OneDrive Gallery URL", value=row.get('gallery_url', ''), key=f"gal_{row['id']}")
                            nt = st.text_area("Notes", value=row.get('notes', ''), key=f"nt_{row['id']}")
                            
                            if st.button("Save Changes", key=f"btn_{row['id']}", use_container_width=True):
                                phone_10 = format_10digit_phone(c_phone)
                                updates = {
                                    "f_rim_serial": fs, 
                                    "r_rim_serial": rs, 
                                    "phone": c_phone, 
                                    "email": c_email, 
                                    "gallery_url": gal, 
                                    "notes": nt
                                }
                                if phone_10:
                                    updates["wp_page_password"] = phone_10

                                success, msg = safe_airtable_update("builds", row['id'], updates)
                                if success:
                                    update_local_record("builds", row['id'], updates)
                                    st.toast("Record details & passkey updated.")
                                    st.rerun()
                                else:
                                    st.error(msg)
                    with c_btn2:
                        with st.popover(f"📮 Delivery{' ✅' if (has_addr or has_tracking) else ''}"):
                            new_addr_input = st.text_area("Delivery Address", value=str(addr_val).strip() if has_addr else "", height=120, key=f"addr_{row['id']}")
                            new_track_input = st.text_input("Courier Tracking Link", value=str(track_val).strip() if has_tracking else "", key=f"track_{row['id']}")
                            if st.button("Save Delivery Info", key=f"addr_btn_{row['id']}", use_container_width=True):
                                updates = {"delivery_address": new_addr_input, "tracking_link": new_track_input}
                                success, msg = safe_airtable_update("builds", row['id'], updates)
                                if success:
                                    update_local_record("builds", row['id'], updates)
                                    st.toast("Delivery info saved.")
                                    st.rerun()
                                else:
                                    st.error(msg)
                    with c_btn3:
                        with st.popover("🖨️ Parts Sheet"):
                            def clean_len(val):
                                try:
                                    return f"{float(val):.1f}" if val and float(val) > 0 else "0.0"
                                except Exception:
                                    return "0.0"
                            txt = f"🚲 WHEELBUILDER LAB SPEC SHEET\n====================================\nCUSTOMER  : {row.get('customer')}\nDATE      : {row.get('date', datetime.now().strftime('%Y-%m-%d'))}\nSPOKE     : {row.get('spoke', 'None')}\nNIPPLE    : {row.get('nipple', 'None')}\n====================================\n"
                            if f_res["exists"]: 
                                txt += f"\n🔘 FRONT WHEEL CONFIGURATION\n  - Rim: {row.get('f_rim')}\n  - Hub: {row.get('f_hub')}\n  - Left Spokes  : {clean_len(row.get('f_l'))} mm\n  - Right Spokes : {clean_len(row.get('f_r'))} mm\n"
                            if r_res["exists"]: 
                                txt += f"\n🔘 REAR WHEEL CONFIGURATION\n  - Rim: {row.get('r_rim')}\n  - Hub: {row.get('r_hub')}\n  - Left Spokes  : {clean_len(row.get('r_l'))} mm\n  - Right Spokes : {clean_len(row.get('r_r'))} mm\n"
                            txt += f"===================================="
                            st.code(txt, language="text")
                            st.download_button(
                                label="📥 Download Parts Sheet", 
                                data=txt, 
                                file_name=f"parts_sheet_{str(row.get('customer')).replace(' ', '_')}.txt", 
                                mime="text/plain", 
                                use_container_width=True
                            )

            st.divider()
            with st.expander(f"📁 Completed Archive ({len(completed_builds)})"):
                if not completed_builds.empty:
                    for _, row in completed_builds.iterrows():
                        with st.expander(f"✅ {row.get('customer')} — {row.get('date')} — {row.get('f_rim')} | {row.get('r_rim')}"):
                            f_weight_snap = safe_int(row.get("f_weight", 0))
                            r_weight_snap = safe_int(row.get("r_weight", 0))
                            
                            f_res, r_res = calculate_wheel_weights(row, st.session_state.data)
                            if f_weight_snap == 0 and f_res["exists"]: 
                                f_weight_snap = safe_int(f_res["total"])
                            if r_weight_snap == 0 and r_res["exists"]: 
                                r_weight_snap = safe_int(r_res["total"])
                                
                            c_spec1, c_spec2, c_spec3 = st.columns(3)
                            with c_spec1:
                                st.markdown("**🔘 FRONT CONFIGURATION**")
                                if f_res["exists"] or str(row.get('f_rim')).lower() != "none":
                                    st.markdown(f"- **Rim:** {row.get('f_rim')}")
                                    st.markdown(f"- **Hub:** {row.get('f_hub')}")
                                    st.markdown(f"- **Spokes:** `Left: {row.get('f_l')}mm / Right: {row.get('f_r')}mm`")
                                    st.metric("Verified Front Weight", f"{f_weight_snap}g")
                                else: 
                                    st.caption("None Configured")
                            with c_spec2:
                                st.markdown("**🔘 REAR CONFIGURATION**")
                                if r_res["exists"] or str(row.get('r_rim')).lower() != "none":
                                    st.markdown(f"- **Rim:** {row.get('r_rim')}")
                                    st.markdown(f"- **Hub:** {row.get('r_hub')}")
                                    st.markdown(f"- **Spokes:** `Left: {row.get('r_l')}mm / Right: {row.get('r_r')}mm`")
                                    st.metric("Verified Rear Weight", f"{r_weight_snap}g")
                                else: 
                                    st.caption("None Configured")
                            with c_spec3:
                                st.markdown("**📦 SYSTEM TOTALS**")
                                st.markdown(f"- **Spoke Model:** {row.get('spoke')}")
                                st.markdown(f"- **Nipple Model:** {row.get('nipple')}")
                                st.metric("System Weight", f"{f_weight_snap + r_weight_snap}g")
                                
                            st.divider()
                            c_arch1, c_arch2 = st.columns([3, 1])
                            with c_arch1:
                                wp_url_val = row.get('wp_page_url')
                                client_pass = format_10digit_phone(row.get('wp_page_password')) or format_10digit_phone(row.get('phone'))
                                if isinstance(wp_url_val, str) and bool(wp_url_val.strip()) and wp_url_val.lower() not in ["none", "nan"]:
                                    st.markdown("**📱 Client Handover Kit**")
                                    client_msg = f"Hi {row.get('customer')}! 👋 Your custom wheelset build is officially finalized and packed! I've created a secure digital build sheet profile for your records.\n\n🔗 Link: {row.get('wp_page_url')}\n🔑 Password: {client_pass}\n\nThis page includes your verified weights, components breakdown sheet, digital invoice copy, and shipping courier tracking records."
                                    st.code(client_msg, language="text")
                            with c_arch2:
                                if st.button("Re-open Build", key=f"re_{row['id']}", use_container_width=True):
                                    success, msg = safe_airtable_update("builds", row['id'], {"status": "Building"})
                                    if success:
                                        update_local_record("builds", row['id'], {"status": "Building"})
                                        st.toast("Build re-opened!")
                                        st.rerun()

    # -------------------------------------------------------------------------
    # TAB 1: STOCK ORDERS MODULE
    # -------------------------------------------------------------------------
    with tabs[1]:
        st.subheader("🚚 Supplier Stock Orders & Delivery Tracker")
        
        df_stock = st.session_state.data.get("stock_orders", pd.DataFrame())
        
        # Summary Metrics
        if not df_stock.empty and 'status' in df_stock.columns:
            active_stock = df_stock[~df_stock['status'].isin(["Delivered", "Cancelled"])]
            delivered_stock = df_stock[df_stock['status'] == "Delivered"]
            
            today_str = datetime.now().strftime("%Y-%m-%d")
            arriving_soon = active_stock[active_stock['eta'].fillna("").astype(str) <= (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")]
            
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("📦 Active Supplier Orders", len(active_stock))
            with m2:
                st.metric("⏳ Arriving Soon / Pending", len(arriving_soon))
            with m3:
                st.metric("✅ Delivered Orders Archive", len(delivered_stock))
        else:
            active_stock = pd.DataFrame()
            delivered_stock = pd.DataFrame()
            st.info("No supplier stock orders recorded yet.")

        st.divider()

        # Log New Stock Order Form
        with st.expander("➕ Log New Supplier Stock Order", expanded=df_stock.empty):
            with st.form("new_stock_order_form"):
                sc1, sc2 = st.columns(2)
                with sc1:
                    sup_name = st.text_input("Supplier Name *", placeholder="e.g. DT Swiss / Wheelbuilder Supplies")
                    st_order_date = st.date_input("Order Date", datetime.now())
                    sup_inv = st.text_input("Supplier Invoice URL / Ref (Optional)", placeholder="e.g. INV-2026-089 or https://...")
                with sc2:
                    st_status = st.selectbox("Initial Status", STOCK_ORDER_STAGES, index=0)
                    st_eta_date = st.date_input("Estimated Delivery (ETA)", datetime.now() + timedelta(days=7))
                    st_track = st.text_input("Courier Tracking Number / Link (Optional)")

                st_items = st.text_area("Product Items & Quantities *", placeholder="e.g. 50x DT Competition Spokes 292mm\n20x Brass Nipples 12mm\n2x RR481 Rims 28H")
                st_notes = st.text_area("Order Notes / PO Reference (Optional)")

                if st.form_submit_button("🚀 Save Stock Order"):
                    if sup_name and st_items:
                        order_payload = {
                            "supplier": sup_name,
                            "order_date": st_order_date.strftime("%Y-%m-%d"),
                            "eta": st_eta_date.strftime("%Y-%m-%d"),
                            "status": st_status,
                            "items": st_items,
                            "supplier_invoice": sup_inv,
                            "tracking_info": st_track,
                            "notes": st_notes
                        }
                        try:
                            # 1 Write API Call with typecast=True
                            new_rec = base.table("stock_orders").create(order_payload, typecast=True)
                            order_payload["id"] = new_rec["id"]
                            add_local_record("stock_orders", order_payload)
                            st.toast("✅ Stock Order Logged!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Failed to log stock order. Please check Airtable table 'stock_orders' exists. Error: {e}")
                    else:
                        st.error("Please enter a Supplier Name and Product Items.")

        # Active Stock Orders Display
        if not active_stock.empty:
            st.write(f"### 📦 Pending Stock Shipments ({len(active_stock)})")
            for _, s_row in active_stock.iterrows():
                s_id = s_row['id']
                s_status = s_row.get('status', 'Ordered')
                s_supplier = s_row.get('supplier', 'Unknown Supplier')
                s_eta = s_row.get('eta', 'TBD')
                s_tracking = s_row.get('tracking_info', '')
                s_invoice = s_row.get('supplier_invoice', '')
                
                has_so_track = isinstance(s_tracking, str) and bool(s_tracking.strip()) and s_tracking.lower() not in ["none", "nan"]
                has_so_inv = isinstance(s_invoice, str) and bool(s_invoice.strip()) and s_invoice.lower() not in ["none", "nan"]

                with st.expander(f"🚚 {s_supplier} — Status: {s_status} | ETA: {s_eta}{' 🚚' if has_so_track else ''}"):
                    sc_col1, sc_col2 = st.columns([3, 2])
                    with sc_col1:
                        st.markdown("**📦 Products & Quantities:**")
                        st.code(s_row.get('items', 'No items listed'), language="text")
                        if s_row.get('notes') and str(s_row.get('notes')).lower() not in ["none", "nan", ""]:
                            st.caption(f"📝 Notes: {s_row.get('notes')}")
                    with sc_col2:
                        st.markdown(f"**Order Date:** {s_row.get('order_date', 'TBD')}")
                        st.markdown(f"**Delivery ETA:** {s_eta}")
                        
                        # Update Status
                        new_so_s = st.selectbox(
                            "Update Status", 
                            STOCK_ORDER_STAGES, 
                            index=STOCK_ORDER_STAGES.index(s_status) if s_status in STOCK_ORDER_STAGES else 0,
                            key=f"so_s_{s_id}"
                        )
                        if new_so_s != s_status:
                            success, msg = safe_airtable_update("stock_orders", s_id, {"status": new_so_s})
                            if success:
                                update_local_record("stock_orders", s_id, {"status": new_so_s})
                                st.toast(f"Stock Order status updated to {new_so_s}!")
                                st.rerun()
                            else:
                                st.error(msg)

                        # Tracking Link / Info
                        if has_so_track:
                            if str(s_tracking).startswith("http"):
                                st.link_button("🚚 Track Package", s_tracking, use_container_width=True)
                            else:
                                st.info(f"Courier Ref: {s_tracking}")

                        # Supplier Invoice Link / Info
                        if has_so_inv:
                            if str(s_invoice).startswith("http"):
                                st.link_button("📄 View Supplier Invoice", s_invoice, use_container_width=True)
                            else:
                                st.caption(f"📄 Invoice Ref: {s_invoice}")

                        # Edit Order Details Popover
                        with st.popover("✏️ Edit Order, Invoice & Tracking"):
                            edit_eta = st.text_input("Delivery ETA (YYYY-MM-DD)", value=str(s_eta), key=f"so_eta_{s_id}")
                            edit_inv = st.text_input("Supplier Invoice URL / Ref", value=str(s_invoice) if has_so_inv else "", key=f"so_inv_{s_id}")
                            edit_track = st.text_input("Tracking Info / URL", value=str(s_tracking) if has_so_track else "", key=f"so_tr_{s_id}")
                            edit_notes = st.text_area("Notes", value=str(s_row.get('notes', '')), key=f"so_nt_{s_id}")
                            
                            if st.button("Save Order Edits", key=f"so_btn_{s_id}", use_container_width=True):
                                updates = {
                                    "eta": edit_eta, 
                                    "supplier_invoice": edit_inv,
                                    "tracking_info": edit_track, 
                                    "notes": edit_notes
                                }
                                success, msg = safe_airtable_update("stock_orders", s_id, updates)
                                if success:
                                    update_local_record("stock_orders", s_id, updates)
                                    st.toast("Order details updated!")
                                    st.rerun()
                                else:
                                    st.error(msg)

        # Delivered & Archive Section
        if not delivered_stock.empty:
            st.divider()
            with st.expander(f"📁 Delivered Stock Order History ({len(delivered_stock)})"):
                for _, s_row in delivered_stock.iterrows():
                    inv_ref = str(s_row.get('supplier_invoice', '')).strip()
                    inv_lbl = f" | Invoice: {inv_ref}" if inv_ref and inv_ref.lower() not in ["none", "nan"] else ""
                    st.markdown(f"**✅ {s_row.get('supplier')}** (Ordered: {s_row.get('order_date', 'N/A')} | ETA: {s_row.get('eta', 'N/A')}{inv_lbl})")
                    st.code(s_row.get('items', ''), language="text")
                    st.write("---")

    # -------------------------------------------------------------------------
    # TAB 2: WORKSHOP TRENDS & ANALYTICS MODULE
    # -------------------------------------------------------------------------
    with tabs[2]:
        st.subheader("📊 Workshop Trends & Analytics Dashboard")
        
        # Scope Filter Toggle (Completed vs All Builds)
        scope_choice = st.radio(
            "Analytics Scope:", 
            ["Completed Builds Only", "All Registered Builds (Active & Completed)"], 
            horizontal=True
        )
        is_completed_only = (scope_choice == "Completed Builds Only")

        analytics = compute_workshop_analytics(st.session_state.data, completed_only=is_completed_only)
        
        if not analytics or analytics.get("total_builds", 0) == 0:
            st.info("No build records found for the selected scope.")
        else:
            df_spk = analytics["df_spk"]
            df_nip = analytics["df_nip"]
            top_rims = analytics["top_rims"]
            top_hubs = analytics["top_hubs"]
            df_processed_builds = analytics["df_builds_processed"]
            rim_holes_map = analytics["rim_holes_map"]

            tot_spokes = df_spk['count'].sum() if not df_spk.empty else 0
            tot_nipples = df_nip['count'].sum() if not df_nip.empty else 0

            # 1. Top Metrics Summary Row
            tm1, tm2, tm3 = st.columns(3)
            with tm1:
                st.metric("🏆 Builds Analyzed", analytics["total_builds"])
            with tm2:
                st.metric("🚲 Total Wheels Built", analytics["total_wheels"])
            with tm3:
                st.metric("📏 Total Spokes Laced", f"{tot_spokes:,}")

            st.divider()

            # 2. Top 10 Rims & Top 10 Hubs Charts
            c_rim_col, c_hub_col = st.columns(2)
            with c_rim_col:
                st.markdown("### 🔘 Top 10 Rims to Date")
                if not top_rims.empty:
                    st.bar_chart(top_rims, color="#00FFCC")
                    rim_df = top_rims.reset_index()
                    rim_df.columns = ["Rim Model", "Build Count"]
                    st.dataframe(rim_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No rim data available.")

            with c_hub_col:
                st.markdown("### ⚙️ Top 10 Hubs to Date")
                if not top_hubs.empty:
                    st.bar_chart(top_hubs, color="#FF9900")
                    hub_df = top_hubs.reset_index()
                    hub_df.columns = ["Hub Model", "Build Count"]
                    st.dataframe(hub_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No hub data available.")

            st.divider()

            # 3. Spokes Consumption Analytics
            st.markdown("### 📏 Spoke Volume Analytics")
            spk_col1, spk_col2 = st.columns(2)
            
            with spk_col1:
                st.markdown("**Spokes Used to Date (by Model)**")
                if not df_spk.empty:
                    spk_summary = df_spk.groupby("model")["count"].sum().sort_values(ascending=False)
                    st.bar_chart(spk_summary, color="#00CCFF")
                    spk_df = spk_summary.reset_index()
                    spk_df.columns = ["Spoke Model", "Total Quantity Used"]
                    st.dataframe(spk_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No spoke data available.")

            with spk_col2:
                st.markdown("**Monthly Spoke Consumption (by Month)**")
                if not df_spk.empty:
                    spk_monthly = df_spk.groupby("month")["count"].sum().sort_index()
                    st.bar_chart(spk_monthly, color="#33FF66")
                    spk_m_df = spk_monthly.reset_index()
                    spk_m_df.columns = ["Month (YYYY-MM)", "Spokes Laced"]
                    st.dataframe(spk_m_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No monthly spoke data available.")

            if not df_spk.empty:
                with st.expander("🔍 Detailed Monthly Spoke Breakdown by Model"):
                    spk_pivot = df_spk.pivot_table(index="month", columns="model", values="count", aggfunc="sum", fill_value=0)
                    st.dataframe(spk_pivot, use_container_width=True)

            st.divider()

            # 4. Nipples Consumption Analytics
            st.markdown("### 🔩 Nipple Volume Analytics")
            nip_col1, nip_col2 = st.columns(2)
            
            with nip_col1:
                st.markdown("**Nipples Used to Date (by Model)**")
                if not df_nip.empty:
                    nip_summary = df_nip.groupby("model")["count"].sum().sort_values(ascending=False)
                    st.bar_chart(nip_summary, color="#FF66CC")
                    nip_df = nip_summary.reset_index()
                    nip_df.columns = ["Nipple Model", "Total Quantity Used"]
                    st.dataframe(nip_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No nipple data available.")

            with nip_col2:
                st.markdown("**Monthly Nipple Consumption (by Month)**")
                if not df_nip.empty:
                    nip_monthly = df_nip.groupby("month")["count"].sum().sort_index()
                    st.bar_chart(nip_monthly, color="#FFCC00")
                    nip_m_df = nip_monthly.reset_index()
                    nip_m_df.columns = ["Month (YYYY-MM)", "Nipples Installed"]
                    st.dataframe(nip_m_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No monthly nipple data available.")

            if not df_nip.empty:
                with st.expander("🔍 Detailed Monthly Nipple Breakdown by Model"):
                    nip_pivot = df_nip.pivot_table(index="month", columns="model", values="count", aggfunc="sum", fill_value=0)
                    st.dataframe(nip_pivot, use_container_width=True)

            st.divider()

            # 5. Interactive Build-by-Build Audit & Verification Tool
            with st.expander("🔎 Audit & Verification: Inspect Individual Build Calculations", expanded=True):
                st.markdown("Select a month to inspect the exact builds and spoke/nipple counts calculated by the system:")
                
                available_months = sorted(list(set(df_spk['month'].tolist())), reverse=True) if not df_spk.empty else []
                if available_months:
                    selected_month = st.selectbox("Filter Audit by Month:", available_months, index=0)
                    
                    audit_rows = []
                    for _, b_row in df_processed_builds.iterrows():
                        b_date = str(b_row.get('date', '')).strip()
                        m_str = b_date[:7] if (b_date and b_date.lower() not in ["none", "nan", ""] and len(b_date) >= 7 and b_date[:4].isdigit()) else "Unspecified Date"
                        
                        if m_str == selected_month:
                            f_rim = str(b_row.get('f_rim', '')).strip()
                            r_rim = str(b_row.get('r_rim', '')).strip()
                            
                            f_cnt = rim_holes_map.get(f_rim.lower(), 28) if (f_rim and f_rim.lower() != "none") else 0
                            r_cnt = rim_holes_map.get(r_rim.lower(), 28) if (r_rim and r_rim.lower() != "none") else 0
                            
                            if f_cnt <= 0 or f_cnt > 48:
                                f_cnt = 28
                            if r_cnt <= 0 or r_cnt > 48:
                                r_cnt = 28
                                
                            tot_spk_b = f_cnt + r_cnt
                            
                            audit_rows.append({
                                "Customer": b_row.get('customer', 'Unknown'),
                                "Date": b_date,
                                "Status": b_row.get('status', 'Unknown'),
                                "Front Rim": f_rim if f_rim else "None",
                                "Rear Rim": r_rim if r_rim else "None",
                                "Front Spokes": f_cnt,
                                "Rear Spokes": r_cnt,
                                "Total Build Spokes": tot_spk_b,
                                "Spoke Model": b_row.get('spoke', 'Unspecified'),
                                "Nipple Model": b_row.get('nipple', 'Unspecified')
                            })
                            
                    df_audit = pd.DataFrame(audit_rows)
                    if not df_audit.empty:
                        st.markdown(f"#### 📜 Builds Analyzed for **{selected_month}** ({len(df_audit)} builds)")
                        st.dataframe(df_audit, use_container_width=True, hide_index=True)
                        st.success(f"🧮 **Verified Total Spokes for {selected_month}:** `{df_audit['Total Build Spokes'].sum():,} spokes` across {len(df_audit)} build sheets.")
                    else:
                        st.info(f"No builds found for {selected_month}.")
                else:
                    st.caption("No month records available to inspect.")

    # -------------------------------------------------------------------------
    # TAB 3: PROVEN RECIPES
    # -------------------------------------------------------------------------
    with tabs[3]:
        st.header("📜 Proven Recipe Archive")
        df_rec_tab = st.session_state.data["spoke_db"]
        if not df_rec_tab.empty:
            r_search = st.text_input("🔍 Search Recipes", key="recipe_search")
            if r_search: 
                df_rec_tab = df_rec_tab[df_rec_tab['label'].astype(str).str.contains(r_search, case=False, na=False)]
            cols_to_show = [c for c in ['label', 'len_l', 'len_r', 'build_count'] if c in df_rec_tab.columns]
            st.dataframe(df_rec_tab[cols_to_show].sort_values('label'), use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------------
    # TAB 4: REGISTER NEW BUILD
    # -------------------------------------------------------------------------
    with tabs[4]:
        st.header("📝 Register New Build")
        st.link_button("⚙️ Open DT Swiss Spoke Calculator", "https://spokes-calculator.dtswiss.com/en/calculator", use_container_width=True)
        st.divider()
        
        rim_opts = ["None"] + sorted([str(x) for x in st.session_state.data["rims"]['label'].dropna().tolist() if str(x).strip()], key=str.lower) if 'label' in st.session_state.data["rims"].columns else ["None"]
        hub_opts = ["None"] + sorted([str(x) for x in st.session_state.data["hubs"]['label'].dropna().tolist() if str(x).strip()], key=str.lower) if 'label' in st.session_state.data["hubs"].columns else ["None"]
        spoke_opts = ["None"] + sorted([str(x) for x in st.session_state.data["spokes"]['label'].dropna().tolist() if str(x).strip()], key=str.lower) if 'label' in st.session_state.data["spokes"].columns else ["None"]
        nipple_opts = ["None"] + sorted([str(x) for x in st.session_state.data["nipples"]['label'].dropna().tolist() if str(x).strip()], key=str.lower) if 'label' in st.session_state.data["nipples"].columns else ["None"]

        with st.form("reg_form_v29"):
            c_cust1, c_cust2, c_cust3 = st.columns(3)
            with c_cust1: 
                cust = st.text_input("Customer Name *")
            with c_cust2: 
                phone_input = st.text_input("Customer Phone (for WhatsApp & Portal Password) *")
            with c_cust3: 
                email_input = st.text_input("Customer Email")

            c_urls1, c_urls2 = st.columns(2)
            with c_urls1: 
                inv = st.text_input("Invoice URL")
            with c_urls2: 
                gal_reg = st.text_input("OneDrive Gallery URL (Optional)")

            c_f, c_r = st.columns(2)
            with c_f:
                st.subheader("Front Wheel")
                fr_rim = st.selectbox("Rim", rim_opts, key="reg_fr")
                fr_hub = st.selectbox("Hub", hub_opts, key="reg_fh")
                fl_len = st.number_input("Left (mm)", step=0.1)
                fr_len = st.number_input("Right (mm)", step=0.1)
            with c_r:
                st.subheader("Rear Wheel")
                rr_rim = st.selectbox("Rim ", rim_opts, key="reg_rr")
                rr_hub = st.selectbox("Hub ", hub_opts, key="reg_rh")
                rl_len = st.number_input("Left (mm) ", step=0.1)
                rr_len = st.number_input("Right (mm) ", step=0.1)
            spk = st.selectbox("Spoke Model", spoke_opts)
            nip = st.selectbox("Nipple Model", nipple_opts)
            notes = st.text_area("Build Notes")
            
            if st.form_submit_button("🚀 Finalize & Register Build"):
                if cust:
                    phone_10 = format_10digit_phone(phone_input)
                    wp_pass = phone_10 if phone_10 else ("WS-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6)))
                    
                    payload = {
                        "customer": cust, 
                        "phone": phone_input,
                        "email": email_input,
                        "date": datetime.now().strftime("%Y-%m-%d"), 
                        "status": "Order Received", 
                        "wp_page_password": wp_pass,
                        "invoice_url": inv, 
                        "gallery_url": gal_reg, 
                        "f_rim": fr_rim, 
                        "f_hub": fr_hub, 
                        "f_l": fl_len, 
                        "f_r": fr_len, 
                        "r_rim": rr_rim, 
                        "r_hub": rr_hub, 
                        "r_l": rl_len, 
                        "r_r": rr_len, 
                        "spoke": spk, 
                        "nipple": nip, 
                        "notes": notes
                    }
                    
                    try:
                        # 1 API Call to create build record with typecast=True
                        new_rec = base.table("builds").create(payload, typecast=True)
                        rec_id = new_rec["id"]
                        
                        wp_link = f"{LIVE_DOMAIN}/?build={rec_id}"
                        payload["id"] = rec_id
                        payload["wp_page_url"] = wp_link
                        
                        # 1 Update call to link page URL
                        safe_airtable_update("builds", rec_id, {"wp_page_url": wp_link})
                        
                        # Append directly to local memory (0 read API calls)
                        add_local_record("builds", payload)

                        # Process spoke recipes locally using pandas (0 read API calls!)
                        db_table = base.table("spoke_db")
                        df_rims = st.session_state.data["rims"]
                        df_hubs = st.session_state.data["hubs"]
                        df_spoke_db = st.session_state.data["spoke_db"]

                        for r, h, l, rr in [(fr_rim, fr_hub, fl_len, fr_len), (rr_rim, rr_hub, rl_len, rr_len)]:
                            if r != "None" and h != "None" and l > 0:
                                matched_rim = df_rims[df_rims['label'] == r] if 'label' in df_rims.columns else pd.DataFrame()
                                matched_hub = df_hubs[df_hubs['label'] == h] if 'label' in df_hubs.columns else pd.DataFrame()
                                
                                if not matched_rim.empty and not matched_hub.empty:
                                    rd_id = matched_rim['id'].values[0]
                                    hd_id = matched_hub['id'].values[0]
                                    fp = f"{r} | {h}"
                                    
                                    # Check local memory first instead of querying Airtable!
                                    exist_match = pd.DataFrame()
                                    if not df_spoke_db.empty and 'label' in df_spoke_db.columns:
                                        exist_match = df_spoke_db[df_spoke_db['label'].astype(str).str.strip().str.lower() == fp.strip().lower()]

                                    if not exist_match.empty:
                                        recipe_row = exist_match.iloc[0]
                                        new_count = safe_int(recipe_row.get('build_count', 1)) + 1
                                        db_table.update(recipe_row['id'], {"build_count": new_count, "len_l": l, "len_r": rr}, typecast=True)
                                        update_local_record("spoke_db", recipe_row['id'], {"build_count": new_count, "len_l": l, "len_r": rr})
                                    else:
                                        new_rec_spk = db_table.create({"rim": [rd_id], "hub": [hd_id], "len_l": l, "len_r": rr, "build_count": 1}, typecast=True)
                                        add_local_record("spoke_db", {
                                            "id": new_rec_spk["id"],
                                            "label": fp,
                                            "len_l": l,
                                            "len_r": rr,
                                            "build_count": 1
                                        })

                        st.success("✅ Build Registered & Client Self-Service Portal Activated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to create build record. Error: {e}")

    # -------------------------------------------------------------------------
    # TAB 5: LIBRARY MANAGEMENT
    # -------------------------------------------------------------------------
    with tabs[5]:
        st.header("📦 Library Management")
        with st.expander("➕ Add New Component"):
            cat = st.radio("Category", ["Rim", "Hub", "Spoke", "Nipple"], horizontal=True)
            with st.form("quick_add_v29"):
                name = st.text_input("Name")
                c1, c2 = st.columns(2)
                p = {}
                if cat == "Rim":
                    p = {
                        "rim": name, 
                        "erd": c1.number_input("ERD"), 
                        "holes": c2.number_input("Holes", value=28), 
                        "weight": st.number_input("Weight")
                    }
                elif cat == "Hub":
                    p = {
                        "hub": name, 
                        "fd_l": c1.number_input("FD-L"), 
                        "fd_r": c2.number_input("FD-R"), 
                        "os_l": c1.number_input("OS-L"), 
                        "os_r": c2.number_input("OS-R"), 
                        "weight": st.number_input("Weight")
                    }
                else:
                    p = {
                        cat.lower(): name, 
                        "weight": st.number_input("Weight (g)", format="%.3f")
                    }
                
                if st.form_submit_button("Save to Database"):
                    if name: 
                        table_key = f"{cat.lower()}s"
                        new_rec = base.table(table_key).create(p, typecast=True)
                        p["id"] = new_rec["id"]
                        p["label"] = name
                        add_local_record(table_key, p)
                        st.success("Added to library!")
                        st.rerun()

        v_cat = st.radio("View Inventory:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
        df_lib = st.session_state.data.get(v_cat, pd.DataFrame())
        if not df_lib.empty: 
            st.dataframe(df_lib.drop(columns=['id', 'label'], errors='ignore').sort_values(df_lib.columns[0]), use_container_width=True, hide_index=True)

# =========================================================================
# --- 5. MODERN SYSTEM ROUTING DISPATCHER ---
# =========================================================================
st.markdown("<style>[data-testid='stSidebar'] { display: none !important; }</style>", unsafe_allow_html=True)

if "build" in st.query_params:
    active_page = st.Page(render_client_portal, title="Client Portal", icon="🚲")
else:
    active_page = st.Page(render_admin_pipeline, title="Admin Dashboard", icon="⚙️")

st.navigation([active_page], position="hidden").run()
