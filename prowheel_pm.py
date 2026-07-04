import streamlit as st
import pandas as pd
import time
import secrets
import string
from datetime import datetime
from pyairtable import Api

# =========================================================================
# --- 1. GLOBAL WORKSHOP CONFIGURATIONS (YOUR CONTROL PANEL) ---
# =========================================================================
LIVE_DOMAIN = "https://wheelbuilder.streamlit.app" if "localhost" not in st.secrets.get("airtable", {}).get("base_id", "") else "http://localhost:8501"
GOOGLE_REVIEW_URL = "https://g.page/r/CVj8dcB7IKHrEAE/review"
CACHE_DATA_TTL = 3600  
WORKSHOP_CAPTION = "Workshop Command Center | Hybrid Architecture Enabled"

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
    """Defensive Engine: Prevents application crashes from bad alphanumeric data entries."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        clean_str = ''.join(c for c in str(val) if c.isdigit() or c == '.')
        try:
            return float(clean_str) if clean_str else default
        except ValueError:
            return default

def get_comp_data_from_bundle(bundle, table_key, label):
    if not label or label == "None": return {}
    df = bundle.get(table_key, pd.DataFrame())
    if df.empty: return {}
    match = df[df['label'].str.lower() == str(label).lower().strip()]
    return match.iloc[0].to_dict() if not match.empty else {}

def calculate_wheel_weights(row, bundle):
    """Calculates weights dynamically using defensive type-safe parsing engines"""
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
    """Client View Module: Securely loads isolated user spec profiles."""
    target_build_id = st.query_params["build"]
    try:
        record = base.table("builds").get(target_build_id)
        row = record.get("fields", {})
        row["id"] = record.get("id")
    except Exception:
        st.error("❌ Invalid or expired build link reference.")
        return

    st.markdown("<h1 style='text-align: center; margin-top:20px;'>🚲 WHEELBUILDER LAB</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Secure Client Verification Portal</p>", unsafe_allow_html=True)
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
            st.info("Please enter your passkey to unlock your custom build metrics.")
            return
        if user_input.strip() != str(correct_password).strip():
            st.error("❌ Incorrect passkey.")
            return
            
        st.session_state[auth_session_key] = True
        st.rerun()

    f_weight_snapshot = int(row.get("f_weight", 0))
    r_weight_snapshot = int(row.get("r_weight", 0))
    f_exists = bool(row.get('f_rim')) and row.get('f_rim') != "None" and f_weight_snapshot > 0
    r_exists = bool(row.get('r_rim')) and row.get('r_rim') != "None" and r_weight_snapshot > 0

    st.markdown(f"## Your Custom Wheelset Build Sheet")
    st.markdown(f"**Client Profile:** {row.get('customer')} | **Completion Date:** {row.get('date')}")
    st.write("Thank you for choosing Wheelbuilder for your custom wheel build!")
    st.success("✨ **Warranty Record:** Your wheels come with a lifetime warranty on the workmanship and spokes.")

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
        if inv_url and inv_url.lower() not in ['none', 'nan', '']: st.link_button("📄 Open Digital Invoice", inv_url, use_container_width=True)
    with c_btn2:
        # FIXED: Removed the rogue 'wildlife' syntax blocker string here
        if track_url and track_url.lower() not in ['none', 'nan', '']: st.link_button("🚚 Track Courier Shipment", track_url, use_container_width=True)
    with c_btn3:
        if gallery_url and gallery_url.lower() not in ['none', 'nan', '']: st.link_button("📸 View Build Gallery", gallery_url, use_container_width=True)
    with c_btn4:
        st.link_button("⭐️ Leave a Google Review", GOOGLE_REVIEW_URL, use_container_width=True)


def render_admin_pipeline():
    """Administrative View Module: Houses complete builder console workflows."""
    if "admin_authenticated" not in st.session_state: st.session_state.admin_authenticated = False

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
                            st.metric("Weight", f"{int(f_res['total'])}g")
                        else: st.write("---")
                    with c2:
                        st.markdown("**🔘 REAR**")
                        if r_res["exists"]:
                            st.markdown(f"**{row.get('r_rim')}**")
                            st.caption(f"{row.get('r_hub')}")
                            st.success(f"📏 L: {row.get('r_l')} / R: {row.get('r_r')} mm")
                            st.metric("Weight", f"{int(r_res['total'])}g")
                        else: st.write("---")
                    with c3:
                        if f_res["exists"] or r_res["exists"]: st.metric("📦 SET", f"{int(f_res['total'] + r_res['total'])}g")
                        cur = row.get('status', 'Order Received')
                        opts = ["Order Received", "Parts Received", "Building", "Complete"]
                        new_s = st.selectbox("Status", opts, index=opts.index(cur) if cur in opts else 0, key=f"s_{row['id']}")
                        
                        if new_s != cur:
                            wp_url_val = row.get('wp_page_url')
                            is_valid_wp = isinstance(wp_url_val, str) and bool(wp_url_val.strip()) and wp_url_val.lower() not in ["none", "nan"]
                            if new_s == "Complete":
                                f_wt_snap = int(f_res["total"]) if f_res["exists"] else 0
                                r_wt_snap = int(r_res["total"]) if r_res["exists"] else 0
                                updates = {"status": new_s, "date": datetime.now().strftime("%Y-%m-%d"), "f_weight": f_wt_snap, "r_weight": r_wt_snap}
                                if not is_valid_wp:
                                    alphabet = string.ascii_uppercase + string.digits
                                    wp_pass = "WS-" + "".join(secrets.choice(alphabet) for _ in range(6))
                                    wp_link = f"{LIVE_DOMAIN}/?build={row['id']}"
                                    updates.update({"wp_page_url": wp_link, "wp_page_password": wp_pass})
                                base.table("builds").update(row['id'], updates)
                                update_local_record("builds", row['id'], updates)
                                st.toast("🎉 Client Profile Synchronized!"); st.rerun()
                            else:
                                base.table("builds").update(row['id'], {"status": new_s})
                                update_local_record("builds", row['id'], {"status": new_s})
                                st.toast(f"Status changed to {new_s}"); st.rerun()
                        
                        c_btn1, c_btn2, c_btn3 = st.columns(3)
                        with c_btn1:
                            with st.popover("📝 Details"):
                                fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                                rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                                gal = st.text_input("OneDrive Gallery URL", value=row.get('gallery_url', ''), key=f"gal_{row['id']}")
                                nt = st.text_area("Notes", value=row.get('notes', ''), key=f"nt_{row['id']}")
                                if st.button("Save Changes", key=f"btn_{row['id']}", use_container_width=True):
                                    updates = {"f_rim_serial": fs, "r_rim_serial": rs, "gallery_url": gal, "notes": nt}
                                    base.table("builds").update(row['id'], updates)
                                    update_local_record("builds", row['id'], updates)
                                    st.toast("Record details updated."); st.rerun()
                        with c_btn2:
                            with st.popover(f"📮 Delivery{' ✅' if (has_addr or has_tracking) else ''}"):
                                new_addr_input = st.text_area("Delivery Address", value=str(addr_val).strip() if has_addr else "", height=120, key=f"addr_{row['id']}")
                                new_track_input = st.text_input("Courier Tracking Link", value=str(track_val).strip() if has_tracking else "", key=f"track_{row['id']}")
                                if st.button("Save Delivery Info", key=f"addr_btn_{row['id']}", use_container_width=True):
                                    base.table("builds").update(row['id'], {"delivery_address": new_addr_input, "tracking_link": new_track_input})
                                    update_local_record("builds", row['id'], {"delivery_address": new_addr_input, "tracking_link": new_track_input})
                                    st.toast("Delivery info saved."); st.rerun()
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

                    wp_url_val = row.get('wp_page_url')
                    if isinstance(wp_url_val, str) and bool(wp_url_val.strip()) and wp_url_val.lower() not in ["none", "nan"]:
                        st.markdown("---")
                        st.markdown("### 📱 Client Handover Kit")
                        client_msg = f"Hi {row.get('customer')}! 👋 Your custom wheelset build is officially finalized and packed! I've created a secure digital build sheet profile for your records.\n\n🔗 Link: {row.get('wp_page_url')}\n🔑 Password: {row.get('wp_page_password')}\n\nThis page includes your verified weights, components breakdown sheet, digital invoice copy, and shipping courier tracking records."
                        st.code(client_msg, language="text")

            st.divider()
            with st.expander(f"📁 Completed Archive ({len(completed_builds)})"):
                if not completed_builds.empty:
                    for _, row in completed_builds.iterrows():
                        with st.expander(f"✅ {row.get('customer')} — {row.get('date')} — {row.get('f_rim')} | {row.get('r_rim')}"):
                            c_arch1, c_arch2 = st.columns([3, 1])
                            with c_arch1:
                                wp_url_val = row.get('wp_page_url')
                                if isinstance(wp_url_val, str) and bool(wp_url_val.strip()) and wp_url_val.lower() not in ["none", "nan"]:
                                    st.markdown("**📱 Client Handover Kit**")
                                    client_msg = f"Hi {row.get('customer')}! 👋 Your custom wheelset build is officially finalized and packed! I've created a secure digital build sheet profile for your records.\n\n🔗 Link: {row.get('wp_page_url')}\n🔑 Password: {row.get('wp_page_password')}\n\nThis page includes your verified weights, components breakdown sheet, digital invoice copy, and shipping courier tracking records."
                                    st.code(client_msg, language="text")
                            with c_arch2:
                                if st.button("Re-open Build", key=f"re_{row['id']}", use_container_width=True):
                                    base.table("builds").update(row['id'], {"status": "Building"})
                                    refresh_api(); st.rerun()

    with tabs[1]:
        st.header("📜 Proven Recipe Archive")
        df_rec_tab = st.session_state.data["spoke_db"]
        if not df_rec_tab.empty:
            r_search = st.text_input("🔍 Search Recipes", key="recipe_search")
            if r_search: df_rec_tab = df_rec_tab[df_rec_tab['label'].str.contains(r_search, case=False, na=False)]
            st.dataframe(df_rec_tab[['label', 'len_l', 'len_r', 'build_count']].sort_values('label'), use_container_width=True, hide_index=True)

    # =========================================================================
    # --- TAB 3: HYBRID FORM REGISTRY WITH STABLE AUTOFILL INJECTION ---
    # =========================================================================
    with tabs[2]:
        st.header("📝 Register New Build")
        st.link_button("⚙️ Open DT Swiss Spoke Calculator", "https://spokes-calculator.dtswiss.com/en/calculator", use_container_width=True)
        st.divider()
        
        rim_opts = ["None"] + sorted(st.session_state.data["rims"]['label'].tolist(), key=str.lower)
        hub_opts = ["None"] + sorted(st.session_state.data["hubs"]['label'].tolist(), key=str.lower)
        spoke_opts = ["None"] + sorted(st.session_state.data["spokes"]['label'].tolist(), key=str.lower)
        nipple_opts = ["None"] + sorted(st.session_state.data["nipples"]['label'].tolist(), key=str.lower)
        df_recipes = st.session_state.data["spoke_db"]

        # Real-time Dropdowns outside the form wrapper stay highly responsive
        st.markdown("### 🔍 Step 1: Select Rims & Hubs")
        c_sel1, c_sel2 = st.columns(2)
        with c_sel1:
            fr_rim = st.selectbox("Front Rim Model", rim_opts, key="reg_fr")
            fr_hub = st.selectbox("Front Hub Model", hub_opts, key="reg_fh")
        with c_sel2:
            rr_rim = st.selectbox("Rear Rim Model", rim_opts, key="reg_rr")
            rr_hub = st.selectbox("Rear Hub Model", hub_opts, key="reg_rh")

        default_fl, default_fr = 0.0, 0.0
        if fr_rim != "None" and fr_hub != "None":
            f_combo = f"{fr_rim} | {fr_hub}"
            f_match = df_recipes[df_recipes['label'] == f_combo] if not df_recipes.empty else pd.DataFrame()
            if not f_match.empty:
                default_fl = safe_float(f_match.iloc[0].get('len_l', 0.0))
                default_fr = safe_float(f_match.iloc[0].get('len_r', 0.0))
                st.success(f"💡 Found Proven Front Recipe: Left {default_fl}mm / Right {default_fr}mm")

        default_rl, default_rr = 0.0, 0.0
        if rr_rim != "None" and rr_hub != "None":
            r_combo = f"{rr_rim} | {rr_hub}"
            r_match = df_recipes[df_recipes['label'] == r_combo] if not df_recipes.empty else pd.DataFrame()
            if not r_match.empty:
                default_rl = safe_float(r_match.iloc[0].get('len_l', 0.0))
                default_rr = safe_float(r_match.iloc[0].get('len_r', 0.0))
                st.success(f"💡 Found Proven Rear Recipe: Left {default_rl}mm / Right {default_rr}mm")

        st.markdown("### 📝 Step 2: Complete Build Metadata")
        
        with st.form(f"build_registration_form_{fr_rim}_{fr_hub}_{rr_rim}_{rr_hub}"):
            cust = st.text_input("Customer Name")
            inv = st.text_input("Invoice URL")
            gal_reg = st.text_input("OneDrive Gallery URL (Optional)")

            c_inp1, c_inputs2 = st.columns(2)
            with c_inp1:
                st.markdown("**Front Spoke Allocation**")
                fl_len = st.number_input("Left Spoke Length (mm)", value=default_fl, step=0.1)
                fr_len = st.number_input("Right Spoke Length (mm)", value=default_fr, step=0.1)
            with c_inputs2:
                st.markdown("**Rear Spoke Allocation**")
                rl_len = st.number_input("Left Spoke Length (mm) ", value=default_rl, step=0.1)
                rr_len = st.number_input("Right Spoke Length (mm) ", value=default_rr, step=0.1)

            spk = st.selectbox("Spoke Model Selection", spoke_opts)
            nip = st.selectbox("Nipple Model Selection", nipple_opts)
            notes = st.text_area("Workshop Build Notes")
            
            if st.form_submit_button("🚀 Finalize & Register Build to Pipeline"):
                if cust:
                    payload = {"customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", "invoice_url": inv, "gallery_url": gal_reg, "f_
