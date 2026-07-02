import streamlit as st
import pandas as pd
import time
import secrets
import string
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v18.16", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    API_KEY = st.secrets["airtable"]["api_key"]
    BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(API_KEY)
    base = api.base(BASE_ID)
except Exception:
    st.error("❌ Airtable Connection Error: Check your Streamlit Secrets.")
    st.stop()

# --- 3. ANALYTICS & SPECIFIC COMPONENT HELPERS ---
def get_comp_data_from_bundle(bundle, table_key, label):
    if not label or label == "None": return {}
    df = bundle.get(table_key, pd.DataFrame())
    if df.empty: return {}
    match = df[df['label'].str.lower() == str(label).lower().strip()]
    return match.iloc[0].to_dict() if not match.empty else {}

def calculate_wheel_weights(row, bundle):
    """Calculates weights dynamically based on row data and component databases"""
    spk_data = get_comp_data_from_bundle(bundle, "spokes", row.get('spoke'))
    nip_data = get_comp_data_from_bundle(bundle, "nipples", row.get('nipple'))
    u_spk = float(spk_data.get('weight', 0))
    u_nip = float(nip_data.get('weight', 0))

    f_res = {"total": 0.0, "exists": False}
    if row.get('f_rim') and row.get('f_rim') != "None":
        frd = get_comp_data_from_bundle(bundle, "rims", row.get('f_rim'))
        fhd = get_comp_data_from_bundle(bundle, "hubs", row.get('f_hub'))
        h = int(frd.get('holes', 0))
        f_res.update({"exists": True, "rim_w": float(frd.get('weight', 0)), "hub_w": float(fhd.get('weight', 0))})
        f_res["total"] = f_res["rim_w"] + f_res["hub_w"] + (h * (u_spk + u_nip))

    r_res = {"total": 0.0, "exists": False}
    if row.get('r_rim') and row.get('r_rim') != "None":
        rrd = get_comp_data_from_bundle(bundle, "rims", row.get('r_rim'))
        rhd = get_comp_data_from_bundle(bundle, "hubs", row.get('r_hub'))
        h = int(rrd.get('holes', 0))
        r_res.update({"exists": True, "rim_w": float(rrd.get('weight', 0)), "hub_w": float(rhd.get('weight', 0))})
        r_res["total"] = r_res["rim_w"] + r_res["hub_w"] + (h * (u_spk + u_nip))
        
    return f_res, r_res

# --- 4. CLIENT PORTAL RENDER ENGINE ---
def render_client_portal(target_build_id):
    """Surgically isolates and displays a single client build sheet with password protection"""
    try:
        with st.spinner("Loading secure build profile..."):
            record = base.table("builds").get(target_build_id)
            row = record.get("fields", {})
            row["id"] = record.get("id")
    except Exception:
        st.error("❌ Invalid or expired build link reference.")
        st.stop()

    # Layout branding header
    st.markdown("<h1 style='text-align: center; margin-top:20px;'>🚲 WHEELBUILDER LAB</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>Secure Client Verification Portal</p>", unsafe_allow_html=True)
    st.divider()

    # Password Gate
    correct_password = row.get("wp_page_password")
    if isinstance(correct_password, float) or not correct_password or str(correct_password).lower() in ["none", "nan"]:
        st.warning("This build sheet has not been assigned a secure access key yet. Please contact the workshop.")
        st.stop()

    c_pass, _ = st.columns([2, 3])
    with c_pass:
        user_input = st.text_input("🔑 Enter your Build Passkey:", type="password", help="Provided to you via WhatsApp or Email")
        
    if not user_input:
        st.info("Please enter the passkey sent to you to unlock your custom build metrics.")
        st.stop()
        
    if user_input.strip() != str(correct_password).strip():
        st.error("❌ Incorrect passkey. Please double-check your records.")
        st.stop()

    # Load lookup tables for portal processing
    all_rims = pd.DataFrame([r['fields'] for r in base.table("rims").all()])
    all_hubs = pd.DataFrame([h['fields'] for h in base.table("hubs").all()])
    all_spokes = pd.DataFrame([s['fields'] for s in base.table("spokes").all()])
    all_nipples = pd.DataFrame([n['fields'] for n in base.table("nipples").all()])
    
    for df, col in [(all_rims, 'rim'), (all_hubs, 'hub'), (all_spokes, 'spoke'), (all_nipples, 'nipple')]:
        if not df.empty and col in df.columns: df['label'] = df[col].astype(str).str.strip()

    client_bundle = {"rims": all_rims, "hubs": all_hubs, "spokes": all_spokes, "nipples": all_nipples}
    f_res, r_res = calculate_wheel_weights(row, client_bundle)

    st.balloons()
    st.markdown(f"## Your Custom Wheelset Build Sheet")
    st.markdown(f"**Client Profile:** {row.get('customer')} | **Completion Date:** {row.get('date')}")
    st.write("Thank you for choosing Wheelbuilder for your custom wheel build! Your wheelset is complete and ready for the road. Below you will find the verified specs, weights, invoice and logistics tracking information.")
    
    st.success("✨ **Warranty Record:** Your wheels come with a lifetime warranty on the workmanship and spokes. If you ever need any support or advice, please get in touch directly.")

    c_front, c_rear = st.columns(2)
    with c_front:
        if f_res["exists"]:
            st.markdown("### 🔘 Front Wheel Configuration")
            st.markdown(f"- **Rim:** {row.get('f_rim')}")
            st.markdown(f"- **Hub:** {row.get('f_hub')}")
            st.markdown(f"- **Spokes:** {row.get('spoke')} `Left: {row.get('f_l')}mm / Right: {row.get('f_r')}mm`")
            st.markdown(f"- **Nipples:** {row.get('nipple')}")
            st.metric("Verified Front Weight", f"{int(f_res['total'])}g")
            
    with c_rear:
        if r_res["exists"]:
            st.markdown("### 🔘 Rear Wheel Configuration")
            st.markdown(f"- **Rim:** {row.get('r_rim')}")
            st.markdown(f"- **Hub:** {row.get('r_hub')}")
            st.markdown(f"- **Spokes:** {row.get('spoke')} `Left: {row.get('r_l')}mm / Right: {row.get('r_r')}mm`")
            st.markdown(f"- **Nipples:** {row.get('nipple')}")
            st.metric("Verified Rear Weight", f"{int(r_res['total'])}g")

    st.divider()
    st.metric("📦 COMPLETE SYSTEM WHEELSET WEIGHT", f"{int(f_res['total'] + r_res['total'])}g")
    st.divider()

    # Logistics & Feedback CTAs
    c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1])
    inv_url = str(row.get('invoice_url', '')).strip()
    track_url = str(row.get('tracking_link', '')).strip()

    with c_btn1:
        if inv_url and inv_url.lower() not in ['none', 'nan', '']:
            st.link_button("📄 Open Digital Invoice", inv_url, use_container_width=True)
    with c_btn2:
        if track_url and track_url.lower() not in ['none', 'nan', '']:
            st.link_button("🚚 Track Courier Shipment", track_url, use_container_width=True)
    with c_btn3:
        # --- NEW GOOGLE REVIEW CTA BUTTON ---
        st.link_button("⭐️ Leave a Google Review", "https://g.page/r/CVj8dcB7IKHrEAE/review", use_container_width=True)

    st.caption("🔒 Secured Archival Record. Property of Wheelbuilder Lab.")
    st.stop()


# --- 5. INITIAL ROUTING CHECK ---
if "build" in st.query_params:
    render_client_portal(st.query_params["build"])


# =========================================================================
# --- 6. ADMIN DASHBOARD ROUTE ---
# =========================================================================

@st.cache_data(ttl=3600, show_spinner="Fetching Workshop Data...")
def fetch_master_bundle():
    tables = {
        "builds": "customer", 
        "rims": "rim", 
        "hubs": "hub", 
        "spokes": "spoke", 
        "nipples": "nipple", 
        "spoke_db": "combo_id"
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
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
            bundle[table_name] = df
            time.sleep(0.2)
        except Exception:
            bundle[table_name] = pd.DataFrame()
    return bundle

if 'data' not in st.session_state:
    st.session_state.data = fetch_master_bundle()

def refresh_api():
    st.cache_data.clear()
    st.session_state.data = fetch_master_bundle()

def update_local_record(table_name, record_id, updates):
    df = st.session_state.data[table_name]
    if not df.empty and record_id in df['id'].values:
        for key, val in updates.items():
            df.loc[df['id'] == record_id, key] = val
        st.session_state.data[table_name] = df


st.caption("Workshop Command Center | Native Secure Customer Portals Enabled")
tabs = st.tabs(["🏁 Workshop", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

with tabs[0]:
    c_head, c_sync = st.columns([5, 1])
    with c_head: st.subheader("🏁 Workshop Pipeline")
    with c_sync:
        if st.button("🔄 Force Sync", use_container_width=True):
            refresh_api(); st.rerun()

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

            addr_val = row.get('delivery_address')
            track_val = row.get('tracking_link')
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
                    else:
                        st.write("---")
                with c2:
                    st.markdown("**🔘 REAR**")
                    if r_res["exists"]:
                        st.markdown(f"**{row.get('r_rim')}**")
                        st.caption(f"{row.get('r_hub')}")
                        st.success(f"📏 L: {row.get('r_l')} / R: {row.get('r_r')} mm")
                        st.metric("Weight", f"{int(r_res['total'])}g")
                    else:
                        st.write("---")
                with c3:
                    if f_res["exists"] or r_res["exists"]:
                        st.metric("📦 SET", f"{int(f_res['total'] + r_res['total'])}g")
                    
                    cur = row.get('status', 'Order Received')
                    opts = ["Order Received", "Parts Received", "Building", "Complete"]
                    new_s = st.selectbox("Status", opts, index=opts.index(cur) if cur in opts else 0, key=f"s_{row['id']}")
                    
                    if new_s != cur:
                        wp_url_val = row.get('wp_page_url')
                        is_valid_wp = isinstance(wp_url_val, str) and bool(wp_url_val.strip()) and wp_url_val.lower() not in ["none", "nan"]

                        if new_s == "Complete" and not is_valid_wp:
                            alphabet = string.ascii_uppercase + string.digits
                            wp_pass = "WS-" + "".join(secrets.choice(alphabet) for _ in range(6))
                            
                            base_url = "https://wheelbuilder.streamlit.app" if "localhost" not in st.secrets.get("airtable", {}).get("base_id", "") else "http://localhost:8501"
                            wp_link = f"{base_url}/?build={row['id']}"
                            
                            updates = {"status": new_s, "wp_page_url": wp_link, "wp_page_password": wp_pass}
                            base.table("builds").update(row['id'], updates)
                            update_local_record("builds", row['id'], updates)
                            st.toast("🎉 Client Web Secure Portal Created inside Streamlit!"); st.rerun()
                        else:
                            base.table("builds").update(row['id'], {"status": new_s})
                            update_local_record("builds", row['id'], {"status": new_s})
                            st.toast(f"Status changed to {new_s}"); st.rerun()
                    
                    c_btn1, c_btn2, c_btn3 = st.columns(3)
                    with c_btn1:
                        with st.popover("📝 Details"):
                            fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                            rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                            nt = st.text_area("Notes", value=row.get('notes', ''), key=f"nt_{row['id']}")
                            if st.button("Save Changes", key=f"btn_{row['id']}", use_container_width=True):
                                base.table("builds").update(row['id'], {"f_rim_serial": fs, "r_rim_serial": rs, "notes": nt})
                                update_local_record("builds", row['id'], {"f_rim_serial": fs, "r_rim_serial": rs, "notes": nt})
                                st.toast("Record updated."); st.rerun()

                    with c_btn2:
                        with st.popover(f"📮 Delivery{' ✅' if (has_addr or has_tracking) else ''}"):
                            st.caption("Delivery address for this build")
                            new_addr_input = st.text_area(
                                "Delivery Address", value=str(addr_val).strip() if has_addr else "", height=120, key=f"addr_{row['id']}"
                            )
                            new_track_input = st.text_input(
                                "Courier Tracking Link", value=str(track_val).strip() if has_tracking else "", key=f"track_{row['id']}"
                            )
                            if has_tracking:
                                st.link_button("🔗 Open Tracking Link", str(track_val).strip(), use_container_width=True)
                                
                            if st.button("Save Delivery Info", key=f"addr_btn_{row['id']}", use_container_width=True):
                                base.table("builds").update(row['id'], {"delivery_address": new_addr_input, "tracking_link": new_track_input})
                                update_local_record("builds", row['id'], {"delivery_address": new_addr_input, "tracking_link": new_track_input})
                                st.toast("Delivery info saved."); st.rerun()
                    
                    with c_btn3:
                        with st.popover("🖨️ Parts Sheet"):
                            txt = f" W_LAB SPEC\nCust: {row.get('customer')}\nRim F: {row.get('f_rim')}\nHub F: {row.get('f_hub')}\nRim R: {row.get('r_rim')}\nHub R: {row.get('r_hub')}"
                            st.code(txt, language="text")

                wp_url_val = row.get('wp_page_url')
                if isinstance(wp_url_val, str) and bool(wp_url_val.strip()) and wp_url_val.lower() not in ["none", "nan"]:
                    st.markdown("---")
                    st.markdown("### 📱 Client Handover Kit")
                    client_msg = (
                        f"Hi {row.get('customer')}! 👋 Your custom wheelset build is officially finalized and packed! "
                        f"I've created a secure digital build sheet profile for your records.\n\n"
                        f"🔗 Link: {row.get('wp_page_url')}\n"
                        f"🔑 Password: {row.get('wp_page_password')}\n\n"
                        f"This page includes your verified weights, components breakdown sheet, digital invoice copy, and shipping courier tracking records."
                    )
                    st.code(client_msg, language="text")

        st.divider()
        
        # --- COMPLETED ARCHIVE EXPANSER ECOSYSTEM ---
        with st.expander(f"📁 Completed Archive ({len(completed_builds)})"):
            if not completed_builds.empty:
                for _, row in completed_builds.iterrows():
                    with st.expander(f"✅ {row.get('customer')} — {row.get('date')} — {row.get('f_rim')} | {row.get('r_rim')}"):
                        c_arch1, c_arch2 = st.columns([3, 1])
                        with c_arch1:
                            wp_url_val = row.get('wp_page_url')
                            if isinstance(wp_url_val, str) and bool(wp_url_val.strip()) and wp_url_val.lower() not in ["none", "nan"]:
                                st.markdown("**📱 Client Handover Kit**")
                                client_msg = (
                                    f"Hi {row.get('customer')}! 👋 Your custom wheelset build is officially finalized and packed! "
                                    f"I've created a secure digital build sheet profile for your records.\n\n"
                                    f"🔗 Link: {row.get('wp_page_url')}\n"
                                    f"🔑 Password: {row.get('wp_page_password')}\n\n"
                                    f"This page includes your verified weights, components breakdown sheet, digital invoice copy, and shipping courier tracking records."
                                )
                                st.code(client_msg, language="text")
                        with c_arch2:
                            if st.button("Re-open Build", key=f"re_{row['id']}", use_container_width=True):
                                base.table("builds").update(row['id'], {"status": "Building", "wp_page_url": "", "wp_page_password": ""})
                                refresh_api(); st.rerun()

# --- TAB 2: PROVEN RECIPES ---
with tabs[1]:
    st.header("📜 Proven Recipe Archive")
    df_rec_tab = st.session_state.data["spoke_db"]
    if not df_rec_tab.empty:
        r_search = st.text_input("🔍 Search Recipes", key="recipe_search")
        if r_search: 
            df_rec_tab = df_rec_tab[df_rec_tab['label'].str.contains(r_search, case=False, na=False)]
        st.dataframe(df_rec_tab[['label', 'len_l', 'len_r', 'build_count']].sort_values('label'), use_container_width=True, hide_index=True)

# --- TAB 3: REGISTER BUILD ---
with tabs[2]:
    st.header("📝 Register New Build")
    st.link_button("⚙️ Open DT Swiss Spoke Calculator", "https://spokes-calculator.dtswiss.com/en/calculator", use_container_width=True)
    st.divider()
    
    rim_opts = ["None"] + sorted(st.session_state.data["rims"]['label'].tolist(), key=str.lower)
    hub_opts = ["None"] + sorted(st.session_state.data["hubs"]['label'].tolist(), key=str.lower)
    spoke_opts = ["None"] + sorted(st.session_state.data["spokes"]['label'].tolist(), key=str.lower)
    nipple_opts = ["None"] + sorted(st.session_state.data["nipples"]['label'].tolist(), key=str.lower)

    with st.form("reg_form_v18_10"):
        cust = st.text_input("Customer Name")
        inv = st.text_input("Invoice URL")
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
                payload = {"customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", "invoice_url": inv,
                           "f_rim": fr_rim, "f_hub": fr_hub, "f_l": fl_len, "f_r": fr_len, "r_rim": rr_rim, "r_hub": rr_hub, "r_l": rl_len, "r_r": rr_len,
                           "spoke": spk, "nipple": nip, "notes": notes}
                base.table("builds").create(payload)

                db_table = base.table("spoke_db")
                df_rims = st.session_state.data["rims"]
                df_hubs = st.session_state.data["hubs"]

                for r, h, l, rr in [(fr_rim, fr_hub, fl_len, fr_len), (rr_rim, rr_hub, rl_len, rr_len)]:
                    if r != "None" and h != "None" and l > 0:
                        rd_id = df_rims[df_rims['label'] == r]['id'].values[0]
                        hd_id = df_hubs[df_hubs['label'] == h]['id'].values[0]
                        fp = f"{r} | {h}".replace("'", "\\'")
                        exist = db_table.all(formula=f"{{combo_id}}='{fp}'")
                        if exist:
                            db_table.update(exist[0]['id'], {"build_count": exist[0]['fields'].get('build_count', 1) + 1, "len_l": l, "len_r": rr})
                        else:
                            db_table.create({"rim": [rd_id], "hub": [hd_id], "len_l": l, "len_r": rr, "build_count": 1})
                
                refresh_api(); st.success("Registered!"); st.rerun()

# --- TAB 4: LIBRARY ---
with tabs[3]:
    st.header("📦 Library Management")
    with st.expander("➕ Add New Component"):
        cat = st.radio("Category", ["Rim", "Hub", "Spoke", "Nipple"], horizontal=True)
        with st.form("quick_add_v18_10"):
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
    if not df_lib.empty:
        st.dataframe(df_lib.drop(columns=['id', 'label'], errors='ignore').sort_values(df_lib.columns[0]), use_container_width=True, hide_index=True)
