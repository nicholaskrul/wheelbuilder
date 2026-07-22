import streamlit as st
import pandas as pd
import time
import secrets
import string
import math
import urllib.parse
from datetime import datetime
from pyairtable import Api

# =========================================================================
# --- 1. GLOBAL WORKSHOP CONFIGURATIONS (YOUR CONTROL PANEL) ---
# =========================================================================
st.set_page_config(page_title="Wheelbuilder Lab Command Center v25", layout="wide", page_icon="🚲")

LIVE_DOMAIN = "https://wheelbuilder.streamlit.app" if "localhost" not in st.secrets.get("airtable", {}).get("base_id", "") else "http://localhost:8501"
GOOGLE_REVIEW_URL = "https://g.page/r/CVj8dcB7IKHrEAE/review"
CACHE_DATA_TTL = 3600  
WORKSHOP_CAPTION = "Workshop Command Center | Production Environment Enabled"

STATUS_STAGES = ["Order Received", "Parts Received", "Building", "Complete"]

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
    """Safely updates Airtable records without crashing Streamlit on missing schema columns."""
    try:
        base.table(table_name).update(record_id, updates)
        return True, "Updated successfully!"
    except Exception as e:
        err_msg = str(e)
        if "UNKNOWN_FIELD_NAME" in err_msg or "422" in err_msg:
            return False, "❌ Airtable Error: Please ensure columns 'phone', 'email', 'wp_page_password', and 'wp_page_url' exist in your Airtable 'builds' table!"
        return False, f"❌ Update Failed: {err_msg}"

def get_comp_data_from_bundle(bundle, table_key, label):
    if not label or label == "None": return {}
    df = bundle.get(table_key, pd.DataFrame())
    if df.empty: return {}
    match = df[df['label'].str.lower() == str(label).lower().strip()]
    return match.iloc[0].to_dict() if not match.empty else {}

def calculate_wheel_weights(row, bundle):
    """Calculates weights dynamically using defensive type-safe parsing engines."""
    spk_data = get_comp_data_from_bundle(bundle, "spokes", row.get('spoke'))
    nip_data = get_comp_data_from_bundle(bundle, "nipples", row.get('nipple'))
    
    u_spk = safe_float(spk_data.get('weight', 0))
    u_nip = safe_float(nip_data.get('weight', 0))

    f_res = {"total": 0.0, "exists": False}
    if row.get('f_rim') and row.get('f_rim') != "None":
        frd = get_comp_data_from_bundle(bundle, "rims", row.get('f_rim'))
        fhd = get_comp_data_from_bundle(bundle, "hubs", row.get('f_hub'))
        h = int(safe_float(frd.get('holes', 0)))
        f_res.update({
            "exists": True, 
            "rim_w": safe_float(frd.get('weight', 0)), 
            "hub_w": safe_float(fhd.get('weight', 0))
        })
        f_res["total"] = f_res["rim_w"] + f_res["hub_w"] + (h * (u_spk + u_nip))

    r_res = {"total": 0.0, "exists": False}
    if row.get('r_rim') and row.get('r_rim') != "None":
        rrd = get_comp_data_from_bundle(bundle, "rims", row.get('r_rim'))
        rhd = get_comp_data_from_bundle(bundle, "hubs", row.get('r_hub'))
        h = int(safe_float(rrd.get('holes', 0)))
        r_res.update({
            "exists": True, 
            "rim_w": safe_float(rrd.get('weight', 0)), 
            "hub_w": safe_float(rhd.get('weight', 0))
        })
        r_res["total"] = r_res["rim_w"] + r_res["hub_w"] + (h * (u_spk + u_nip))
        
    return f_res, r_res

def format_clean_phone(phone_str):
    """Cleans phone numbers for WhatsApp integration."""
    if not phone_str: return ""
    clean = "".join(c for c in str(phone_str) if c.isdigit())
    if clean.startswith("0"):
        clean = "27" + clean[1:]  # Default South Africa format; adjust leading country code if needed
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
        f"🔑 Passkey: {passkey}\n\n"
        f"Let us know if you have any questions!"
    )
    return msg

@st.cache_data(ttl=CACHE_DATA_TTL, show_spinner="Fetching Workshop Data...")
def fetch_master_bundle():
    tables = {"builds": "customer", "rims": "rim", "hubs": "hub", "spokes": "spoke", "nipples": "nipple", "spoke_db": "combo_id"}
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
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
            bundle[table_name] = df
            time.sleep(0.1)
        except Exception:
            bundle[table_name] = pd.DataFrame()
    return bundle

# =========================================================================
# --- 4. FUNCTIONAL PAGE MODULES ---
# =========================================================================

def render_client_portal():
    """Client View Module: Securely loads isolated user spec profiles & live progress."""
    # --- BLACK BRANDING THEME INJECTION ---
    st.markdown("""
        <style>
        /* Main background */
        .stApp {
            background-color: #000000 !important;
            color: #FFFFFF !important;
        }
        /* Universal Text Elements */
        h1, h2, h3, h4, h5, h6, p, label, span, div {
            color: #FFFFFF !important;
        }
        /* Secondary Text Subtitles */
        .portal-subtitle {
            text-align: center;
            color: #A0A0A0 !important;
            margin-top: 5px;
        }
        /* Metrics styling */
        [data-testid="stMetricValue"] {
            color: #00FFCC !important;
        }
        [data-testid="stMetricLabel"] {
            color: #D0D0D0 !important;
        }
        /* Form Inputs */
        .stTextInput input {
            background-color: #121212 !important;
            color: #FFFFFF !important;
            border: 1px solid #333333 !important;
        }
        /* Horizontal Rule */
        hr {
            border-color: #222222 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    target_build_id = st.query_params["build"]
    try:
        record = base.table("builds").get(target_build_id)
        row = record.get("fields", {})
        row["id"] = record.get("id")
    except Exception:
        st.error("❌ Invalid or expired build link reference.")
        return

    # --- BRAND LOGO HEADER ---
    c_logo1, c_logo2, c_logo3 = st.columns([2, 1, 2])
    with c_logo2:
        try:
            st.image("WB_logo.png", use_container_width=True)
        except Exception:
            st.markdown("<h1 style='text-align: center;'>🚲 WHEELBUILDER LAB</h1>", unsafe_allow_html=True)

    st.markdown("<p class='portal-subtitle'>Secure Self-Service Build Portal</p>", unsafe_allow_html=True)
    st.divider()

    auth_session_key = f"auth_{target_build_id}"
    if auth_session_key not in st.session_state:
        st.session_state[auth_session_key] = False

    if not st.session_state[auth_session_key]:
        correct_password = row.get("wp_page_password")
        if isinstance(correct_password, float) or not correct_password or str(correct_password).lower() in ["none", "nan"]:
            st.warning("This build sheet has not been assigned an access key yet.")
            return

        c_pass, _ = st.columns([2, 3])
        with c_pass:
            user_input = st.text_input("🔑 Enter your Build Passkey:", type="password")
        if not user_input:
            st.info("Please enter your passkey to unlock your custom build portal.")
            return
        if user_input.strip() != str(correct_password).strip():
            st.error("❌ Incorrect passkey.")
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

    # --- WORKSHOP NOTES SECTION ---
    build_notes = str(row.get('notes', '')).strip()
    if build_notes and build_notes.lower() not in ["none", "nan", ""]:
        st.info(f"📢 **Workshop Update Note:** {build_notes}")

    st.divider()

    # --- DYNAMIC WEIGHT COMPUTATION ENGINE ---
    bundle = fetch_master_bundle()
    f_res, r_res = calculate_wheel_weights(row, bundle)

    f_weight_snap = safe_int(row.get("f_weight", 0))
    r_weight_snap = safe_int(row.get("r_weight", 0))

    f_weight_disp = f_weight_snap if f_weight_snap > 0 else safe_int(f_res["total"])
    r_weight_disp = r_weight_snap if r_weight_snap > 0 else safe_int(r_res["total"])

    f_exists = f_res["exists"] or (bool(row.get('f_rim')) and row.get('f_rim') != "None")
    r_exists = r_res["exists"] or (bool(row.get('r_rim')) and row.get('r_rim') != "None")

    st.markdown(f"## Custom Wheelset Build Sheet")
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
        if inv_url and inv_url.lower() not in ['none', 'nan', '']: st.link_button("📄 Open Digital Invoice", inv_url, use_container_width=True)
    with c_btn2:
        if track_url and track_url.lower() not in ['none', 'nan', '']: st.link_button("🚚 Track Courier Shipment", track_url, use_container_width=True)
    with c_btn3:
        if gallery_url and gallery_url.lower() not in ['none', 'nan', '']: st.link_button("📸 View Build Gallery", gallery_url, use_container_width=True)
    with c_btn4:
        st.link_button("⭐️ Leave a Google Review", GOOGLE_REVIEW_URL, use_container_width=True)


def render_admin_pipeline():
    """Administrative View Module: Houses complete builder console workflows."""
    if "admin_authenticated" not in st.session_state: st.session_state.admin_authenticated = False

    # Secret Trusted Device Token Entrance Pattern
    if "staff" in st.query_params and st.query_params["staff"] == "LAB_STAFF_2026":
        st.session_state.admin_authenticated = True

    if not st.session_state.admin_authenticated:
        st.markdown("<h2 style='margin-top:40px;'>🔓 Workshop Administration Panel</h2>", unsafe_allow_html=True)
        st.divider()
        c_login, _ = st.columns([2, 3])
        with c_login:
            user_entered_password = st.text_input("Enter Master Password:", type="password")
            if st.button("Unlock Workshop Console", use_container_width=True):
                if user_entered_password == st.secrets["admin"]["password"]:
                    st.session_state.admin_authenticated = True
                    st.toast("Access Granted.")
                    st.rerun()
                else: st.error("❌ Invalid Password.")
        return

    if 'data' not in st.session_state: st.session_state.data = fetch_master_bundle()
    def refresh_api():
        st.cache_data.clear()
        st.session_state.data = fetch_master_bundle()
    def update_local_record(table_name, record_id, updates):
        df = st.session_state.data[table_name]
        if not df.empty and record_id in df['id'].values:
            for key, val in updates.items(): df.loc[df['id'] == record_id, key] = val
            st.session_state.data[table_name] = df

    st.title("🚲 Wheelbuilder Lab Command Center")
    st.caption(WORKSHOP_CAPTION)
    
    tabs = st.tabs(["🏁 Workshop", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

    # -------------------------------------------------------------------------
    # TAB 0: WORKSHOP PIPELINE
    # -------------------------------------------------------------------------
    with tabs[0]:
        c_head, c_sync = st.columns([5, 1])
        with c_head: st.subheader("🏁 Workshop Pipeline")
        with c_sync:
            if st.button("🔄 Force Sync", use_container_width=True): refresh_api(); st.rerun()

        df_builds = st.session_state.data["builds"]
        if df_builds.empty: st.info("No active builds found.")
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
                        else: st.write("---")
                    with c2:
                        st.markdown("**🔘 REAR**")
                        if r_res["exists"]:
                            st.markdown(f"**{row.get('r_rim')}**")
                            st.caption(f"{row.get('r_hub')}")
                            st.success(f"📏 L: {row.get('r_l')} / R: {row.get('r_r')} mm")
                            st.metric("Est Weight", f"{safe_int(r_res['total'])}g")
                        else: st.write("---")
                    with c3:
                        if f_res["exists"] or r_res["exists"]: st.metric("📦 EST SET", f"{safe_int(f_res['total'] + r_res['total'])}g")
                        cur = row.get('status', 'Order Received')
                        new_s = st.selectbox("Status", STATUS_STAGES, index=STATUS_STAGES.index(cur) if cur in STATUS_STAGES else 0, key=f"s_{row['id']}")
                        
                        if new_s != cur:
                            updates = {"status": new_s}

                            # AUTO-GENERATE PORTAL PASSKEY FOR EXISTING BUILDS IF MISSING
                            wp_pass = row.get("wp_page_password")
                            if not wp_pass or str(wp_pass).lower() in ["none", "nan", ""]:
                                alphabet = string.ascii_uppercase + string.digits
                                generated_pass = "WS-" + "".join(secrets.choice(alphabet) for _ in range(6))
                                generated_url = f"{LIVE_DOMAIN}/?build={row['id']}"
                                updates.update({
                                    "wp_page_password": generated_pass,
                                    "wp_page_url": generated_url
                                })

                            if new_s == "Complete":
                                f_wt_snap = safe_int(f_res["total"]) if f_res["exists"] else 0
                                r_wt_snap = safe_int(r_res["total"]) if r_res["exists"] else 0
                                updates.update({"date": datetime.now().strftime("%Y-%m-%d"), "f_weight": f_wt_snap, "r_weight": r_wt_snap})
                            
                            success, msg = safe_airtable_update("builds", row['id'], updates)
                            if success:
                                update_local_record("builds", row['id'], updates)
                                st.toast(f"Status updated to {new_s}!")
                                st.rerun()
                            else:
                                st.error(msg)

                    # --- SEMI-AUTOMATED DISPATCH PANEL ---
                    phone = row.get("phone", "")
                    email = row.get("email", "")
                    portal_url = row.get("wp_page_url", f"{LIVE_DOMAIN}/?build={row['id']}")
                    passkey = row.get("wp_page_password", "")

                    with st.popover("📲 Send Status Update to Client"):
                        st.markdown("#### Send Notification")
                        
                        if not passkey or str(passkey).lower() in ["none", "nan", ""]:
                            st.warning("⚠️ This build does not have a portal passkey yet.")
                            if st.button("🔑 Generate Portal Key Now", key=f"gen_key_{row['id']}", use_container_width=True):
                                alphabet = string.ascii_uppercase + string.digits
                                gen_pass = "WS-" + "".join(secrets.choice(alphabet) for _ in range(6))
                                gen_url = f"{LIVE_DOMAIN}/?build={row['id']}"
                                updates = {"wp_page_password": gen_pass, "wp_page_url": gen_url}
                                
                                success, msg = safe_airtable_update("builds", row['id'], updates)
                                if success:
                                    update_local_record("builds", row['id'], updates)
                                    st.toast("Portal passkey generated!")
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
                                updates = {
                                    "f_rim_serial": fs, 
                                    "r_rim_serial": rs, 
                                    "phone": c_phone, 
                                    "email": c_email, 
                                    "gallery_url": gal, 
                                    "notes": nt
                                }
                                success, msg = safe_airtable_update("builds", row['id'], updates)
                                if success:
                                    update_local_record("builds", row['id'], updates)
                                    st.toast("Record details updated.")
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
                                try: return f"{float(val):.1f}" if val and float(val) > 0 else "0.0"
                                except: return "0.0"
                            txt = f"🚲 WHEELBUILDER LAB SPEC SHEET\n====================================\nCUSTOMER  : {row.get('customer')}\nDATE      : {row.get('date', datetime.now().strftime('%Y-%m-%d'))}\nSPOKE     : {row.get('spoke', 'None')}\nNIPPLE    : {row.get('nipple', 'None')}\n====================================\n"
                            if f_res["exists"]: txt += f"\n🔘 FRONT WHEEL CONFIGURATION\n  - Rim: {row.get('f_rim')}\n  - Hub: {row.get('f_hub')}\n  - Left Spokes  : {clean_len(row.get('f_l'))} mm\n  - Right Spokes : {clean_len(row.get('f_r'))} mm\n"
                            if r_res["exists"]: txt += f"\n🔘 REAR WHEEL CONFIGURATION\n  - Rim: {row.get('r_rim')}\n  - Hub: {row.get('r_hub')}\n  - Left Spokes  : {clean_len(row.get('r_l'))} mm\n  - Right Spokes : {clean_len(row.get('r_r'))} mm\n"
                            txt += f"===================================="
                            st.code(txt, language="text")
                            st.download_button(label="📥 Download Parts Sheet", data=txt, file_name=f"parts_sheet_{str(row.get('customer')).replace(' ', '_')}.txt", mime="text/plain", use_container_width=True)

            st.divider()
            with st.expander(f"📁 Completed Archive ({len(completed_builds)})"):
                if not completed_builds.empty:
                    for _, row in completed_builds.iterrows():
                        with st.expander(f"✅ {row.get('customer')} — {row.get('date')} — {row.get('f_rim')} | {row.get('r_rim')}"):
                            f_weight_snap = safe_int(row.get("f_weight", 0))
                            r_weight_snap = safe_int(row.get("r_weight", 0))
                            
                            f_res, r_res = calculate_wheel_weights(row, st.session_state.data)
                            if f_weight_snap == 0 and f_res["exists"]: f_weight_snap = safe_int(f_res["total"])
                            if r_weight_snap == 0 and r_res["exists"]: r_weight_snap = safe_int(r_res["total"])
                                
                            c_spec1, c_spec2, c_spec3 = st.columns(3)
                            with c_spec1:
                                st.markdown("**🔘 FRONT CONFIGURATION**")
                                if f_res["exists"] or row.get('f_rim') != "None":
                                    st.markdown(f"- **Rim:** {row.get('f_rim')}")
                                    st.markdown(f"- **Hub:** {row.get('f_hub')}")
                                    st.markdown(f"- **Spokes:** `Left: {row.get('f_l')}mm / Right: {row.get('f_r')}mm`")
                                    st.metric("Verified Front Weight", f"{f_weight_snap}g")
                                else: st.caption("None Configured")
                            with c_spec2:
                                st.markdown("**🔘 REAR CONFIGURATION**")
                                if r_res["exists"] or row.get('r_rim') != "None":
                                    st.markdown(f"- **Rim:** {row.get('r_rim')}")
                                    st.markdown(f"- **Hub:** {row.get('r_hub')}")
                                    st.markdown(f"- **Spokes:** `Left: {row.get('r_l')}mm / Right: {row.get('r_r')}mm`")
                                    st.metric("Verified Rear Weight", f"{r_weight_snap}g")
                                else: st.caption("None Configured")
                            with c_spec3:
                                st.markdown("**📦 SYSTEM TOTALS**")
                                st.markdown(f"- **Spoke Model:** {row.get('spoke')}")
                                st.markdown(f"- **Nipple Model:** {row.get('nipple')}")
                                st.metric("System Weight", f"{f_weight_snap + r_weight_snap}g")
                                
                            st.divider()
                            c_arch1, c_arch2 = st.columns([3, 1])
                            with c_arch1:
                                wp_url_val = row.get('wp_page_url')
                                if isinstance(wp_url_val, str) and bool(wp_url_val.strip()) and wp_url_val.lower() not in ["none", "nan"]:
                                    st.markdown("**📱 Client Handover Kit**")
                                    client_msg = f"Hi {row.get('customer')}! 👋 Your custom wheelset build is officially finalized and packed! I've created a secure digital build sheet profile for your records.\n\n🔗 Link: {row.get('wp_page_url')}\n🔑 Password: {row.get('wp_page_password')}\n\nThis page includes your verified weights, components breakdown sheet, digital invoice copy, and shipping courier tracking records."
                                    st.code(client_msg, language="text")
                            with c_arch2:
                                if st.button("Re-open Build", key=f"re_{row['id']}", use_container_width=True):
                                    safe_airtable_update("builds", row['id'], {"status": "Building"})
                                    refresh_api(); st.rerun()

    # -------------------------------------------------------------------------
    # TAB 1: PROVEN RECIPES
    # -------------------------------------------------------------------------
    with tabs[1]:
        st.header("📜 Proven Recipe Archive")
        df_rec_tab = st.session_state.data["spoke_db"]
        if not df_rec_tab.empty:
            r_search = st.text_input("🔍 Search Recipes", key="recipe_search")
            if r_search: df_rec_tab = df_rec_tab[df_rec_tab['label'].str.contains(r_search, case=False, na=False)]
            st.dataframe(df_rec_tab[['label', 'len_l', 'len_r', 'build_count']].sort_values('label'), use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------------
    # TAB 2: REGISTER NEW BUILD
    # -------------------------------------------------------------------------
    with tabs[2]:
        st.header("📝 Register New Build")
        st.link_button("⚙️ Open DT Swiss Spoke Calculator", "https://spokes-calculator.dtswiss.com/en/calculator", use_container_width=True)
        st.divider()
        rim_opts = ["None"] + sorted(st.session_state.data["rims"]['label'].tolist(), key=str.lower)
        hub_opts = ["None"] + sorted(st.session_state.data["hubs"]['label'].tolist(), key=str.lower)
        spoke_opts = ["None"] + sorted(st.session_state.data["spokes"]['label'].tolist(), key=str.lower)
        nipple_opts = ["None"] + sorted(st.session_state.data["nipples"]['label'].tolist(), key=str.lower)

        with st.form("reg_form_v25"):
            c_cust1, c_cust2, c_cust3 = st.columns(3)
            with c_cust1: cust = st.text_input("Customer Name *")
            with c_cust2: phone_input = st.text_input("Customer Phone (for WhatsApp updates)")
            with c_cust3: email_input = st.text_input("Customer Email")

            c_urls1, c_urls2 = st.columns(2)
            with c_urls1: inv = st.text_input("Invoice URL")
            with c_urls2: gal_reg = st.text_input("OneDrive Gallery URL (Optional)")

            c_f, c_r = st.columns(2)
            with c_f:
                st.subheader("Front Wheel")
                fr_rim = st.selectbox("Rim", rim_opts, key="reg_fr")
                fr_hub = st.selectbox("Hub", hub_opts, key="reg_fh")
                fl_len, fr_len = st.number_input("Left (mm)", step=0.1), st.number_input("Right (mm)", step=0.1)
            with c_r:
                st.subheader("Rear Wheel")
                rr_rim = st.selectbox("Rim ", rim_opts, key="reg_rr")
                rr_hub = st.selectbox("Hub ", hub_opts, key="reg_rh")
                rl_len, rr_len = st.number_input("Left (mm) ", step=0.1), st.number_input("Right (mm) ", step=0.1)
            spk = st.selectbox("Spoke Model", spoke_opts)
            nip = st.selectbox("Nipple Model", nipple_opts)
            notes = st.text_area("Build Notes")
            
            if st.form_submit_button("🚀 Finalize & Register Build"):
                if cust:
                    alphabet = string.ascii_uppercase + string.digits
                    wp_pass = "WS-" + "".join(secrets.choice(alphabet) for _ in range(6))
                    
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
                        new_rec = base.table("builds").create(payload)
                        rec_id = new_rec["id"]
                        
                        wp_link = f"{LIVE_DOMAIN}/?build={rec_id}"
                        safe_airtable_update("builds", rec_id, {"wp_page_url": wp_link})

                        db_table = base.table("spoke_db")
                        df_rims = st.session_state.data["rims"]
                        df_hubs = st.session_state.data["hubs"]
                        for r, h, l, rr in [(fr_rim, fr_hub, fl_len, fr_len), (rr_rim, rr_hub, rl_len, rr_len)]:
                            if r != "None" and h != "None" and l > 0:
                                matched_rim = df_rims[df_rims['label'] == r]
                                matched_hub = df_hubs[df_hubs['label'] == h]
                                
                                if not matched_rim.empty and not matched_hub.empty:
                                    rd_id = matched_rim['id'].values[0]
                                    hd_id = matched_hub['id'].values[0]
                                    fp = f"{r} | {h}".replace("'", "\\'")
                                    exist = db_table.all(formula=f"{{combo_id}}='{fp}'")
                                    if exist: db_table.update(exist[0]['id'], {"build_count": exist[0]['fields'].get('build_count', 1) + 1, "len_l": l, "len_r": rr})
                                    else: db_table.create({"rim": [rd_id], "hub": [hd_id], "len_l": l, "len_r": rr, "build_count": 1})
                        
                        refresh_api()
                        st.success("✅ Build Registered & Client Self-Service Portal Activated!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to create build record. Please check that Airtable columns 'phone', 'email', 'wp_page_password', and 'wp_page_url' exist in your base. Error: {e}")

    # -------------------------------------------------------------------------
    # TAB 3: LIBRARY MANAGEMENT
    # -------------------------------------------------------------------------
    with tabs[3]:
        st.header("📦 Library Management")
        with st.expander("➕ Add New Component"):
            cat = st.radio("Category", ["Rim", "Hub", "Spoke", "Nipple"], horizontal=True)
            with st.form("quick_add_v25"):
                name = st.text_input("Name")
                c1, c2 = st.columns(2)
                p = {}
                if cat == "Rim": p = {"rim": name, "erd": c1.number_input("ERD"), "holes": c2.number_input("Holes", value=28), "weight": st.number_input("Weight")}
                elif cat == "Hub": p = {"hub": name, "fd_l": c1.number_input("FD-L"), "fd_r": c2.number_input("FD-R"), "os_l": c1.number_input("OS-L"), "os_r": c2.number_input("OS-R"), "weight": st.number_input("Weight")}
                else: p = {cat.lower(): name, "weight": st.number_input("Weight (g)", format="%.3f")}
                if st.form_submit_button("Save to Database"):
                    if name: 
                        base.table(f"{cat.lower()}s").create(p)
                        refresh_api(); st.success("Added!"); st.rerun()
        v_cat = st.radio("View Inventory:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
        df_lib = st.session_state.data[v_cat]
        if not df_lib.empty: st.dataframe(df_lib.drop(columns=['id', 'label'], errors='ignore').sort_values(df_lib.columns[0]), use_container_width=True, hide_index=True)

# =========================================================================
# --- 5. MODERN SYSTEM ROUTING DISPATCHER ---
# =========================================================================
st.markdown("<style>[data-testid='stSidebar'] { display: none !important; }</style>", unsafe_allow_html=True)

if "build" in st.query_params:
    active_page = st.Page(render_client_portal, title="Client Portal", icon="🚲")
else:
    active_page = st.Page(render_admin_pipeline, title="Admin Dashboard", icon="⚙️")

st.navigation([active_page], position="hidden").run()
