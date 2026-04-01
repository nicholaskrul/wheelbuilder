import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v18.9.1", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    API_KEY = st.secrets["airtable"]["api_key"]
    BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(API_KEY)
    base = api.base(BASE_ID)
except Exception:
    st.error("❌ Airtable Connection Error: Check your Streamlit Secrets.")
    st.stop()

# --- 3. THE OPTIMIZED DATA ENGINE (API SAVER) ---
@st.cache_data(ttl=3600, show_spinner="Fetching Workshop Data...")
def fetch_master_bundle():
    """
    Fetches all 6 tables in a single operation. 
    TTL set to 1 hour to drastically reduce API calls.
    """
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
            # Flatten Airtable lookup/link arrays
            for col in df.columns:
                df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
            bundle[table_name] = df
            time.sleep(0.2) # Small gap to prevent 429 errors
        except Exception:
            bundle[table_name] = pd.DataFrame()
    return bundle

# --- 4. STATE & SYNC MANAGEMENT ---
if 'data' not in st.session_state:
    st.session_state.data = fetch_master_bundle()

def refresh_api():
    """Manual trigger to bypass the 1-hour cache and get fresh data."""
    st.cache_data.clear()
    st.session_state.data = fetch_master_bundle()

def update_local_record(table_name, record_id, updates):
    """
    Mirror Airtable changes in the local session state.
    This allows the UI to update without re-fetching all data from the API.
    """
    df = st.session_state.data[table_name]
    if not df.empty and record_id in df['id'].values:
        for key, val in updates.items():
            df.loc[df['id'] == record_id, key] = val
        st.session_state.data[table_name] = df

# --- 5. ANALYTICS HELPERS ---
def get_comp_data(table_key, label):
    df = st.session_state.data.get(table_key, pd.DataFrame())
    if df.empty or not label: return {}
    match = df[df['label'].str.lower() == str(label).lower().strip()]
    return match.iloc[0].to_dict() if not match.empty else {}

# --- 6. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v18.9.1")
st.caption("Workshop Command Center | API Conservation Mode")

tabs = st.tabs(["🏁 Workshop", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

# --- TAB 1: WORKSHOP (PIPELINE) ---
with tabs[0]:
    c_head, c_sync = st.columns([5, 1])
    with c_head: st.subheader("🏁 Workshop Pipeline")
    with c_sync:
        if st.button("🔄 Force Sync", use_container_width=True):
            refresh_api(); st.rerun()

    df_builds = st.session_state.data["builds"]
    df_rims = st.session_state.data["rims"]
    df_hubs = st.session_state.data["hubs"]
    df_spokes = st.session_state.data["spokes"]
    df_nipples = st.session_state.data["nipples"]

    if df_builds.empty:
        st.info("No active builds found. Start by registering a new build.")
    else:
        # Resilient filtering for Active vs Complete
        active_mask = df_builds['status'].fillna("Order Received") != "Complete"
        active_builds = df_builds[active_mask].sort_values('id', ascending=False)
        completed_builds = df_builds[~active_mask].sort_values('id', ascending=False)

        st.write(f"### 🛠️ Active Builds ({len(active_builds)})")
        for _, row in active_builds.iterrows():
            # Get Hardware Weights
            spk_data = get_comp_data("spokes", row.get('spoke'))
            nip_data = get_comp_data("nipples", row.get('nipple'))
            u_spk, u_nip = float(spk_data.get('weight', 0)), float(nip_data.get('weight', 0))

            f_res = {"total": 0.0, "exists": False}
            if row.get('f_rim'):
                frd, fhd = get_comp_data("rims", row.get('f_rim')), get_comp_data("hubs", row.get('f_hub'))
                h = int(frd.get('holes', 0))
                f_res.update({"exists": True, "rim_w": float(frd.get('weight', 0)), "hub_w": float(fhd.get('weight', 0))})
                f_res["total"] = f_res["rim_w"] + f_res["hub_w"] + (h * (u_spk + u_nip))

            r_res = {"total": 0.0, "exists": False}
            if row.get('r_rim'):
                rrd, rhd = get_comp_data("rims", row.get('r_rim')), get_comp_data("hubs", row.get('r_hub'))
                h = int(rrd.get('holes', 0))
                r_res.update({"exists": True, "rim_w": float(rrd.get('weight', 0)), "hub_w": float(rhd.get('weight', 0))})
                r_res["total"] = r_res["rim_w"] + r_res["hub_w"] + (h * (u_spk + u_nip))

            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**🔘 FRONT**")
                    if f_res["exists"]:
                        st.markdown(f"**{row.get('f_rim')}**")
                        st.caption(f"{row.get('f_hub')}")
                        st.info(f"📏 L: {row.get('f_l')} / R: {row.get('f_r')} mm")
                        st.metric("Weight", f"{int(f_res['total'])}g")
                with c2:
                    st.markdown("**🔘 REAR**")
                    if r_res["exists"]:
                        st.markdown(f"**{row.get('r_rim')}**")
                        st.caption(f"{row.get('r_hub')}")
                        st.success(f"📏 L: {row.get('r_l')} / R: {row.get('r_r')} mm")
                        st.metric("Weight", f"{int(r_res['total'])}g")
                with c3:
                    st.metric("📦 SET", f"{int(f_res['total'] + r_res['total'])}g")
                    cur = row.get('status', 'Order Received')
                    opts = ["Order Received", "Parts Received", "Building", "Complete"]
                    new_s = st.selectbox("Status", opts, index=opts.index(cur) if cur in opts else 0, key=f"s_{row['id']}")
                    
                    if new_s != cur:
                        # Update Cloud
                        base.table("builds").update(row['id'], {"status": new_s})
                        # Update Local
                        update_local_record("builds", row['id'], {"status": new_s})
                        st.toast(f"Status changed to {new_s}"); st.rerun()
                    
                    with st.popover("📝 Details / Serial #"):
                        fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                        rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                        nt = st.text_area("Notes", value=row.get('notes', ''), key=f"nt_{row['id']}")
                        if st.button("Save Changes", key=f"btn_{row['id']}", use_container_width=True):
                            base.table("builds").update(row['id'], {"f_rim_serial": fs, "r_rim_serial": rs, "notes": nt})
                            update_local_record("builds", row['id'], {"f_rim_serial": fs, "r_rim_serial": rs, "notes": nt})
                            st.toast("Updated locally and in cloud."); st.rerun()

        # --- ARCHIVE (Fixed Variable Name Error) ---
        st.divider()
        with st.expander(f"📁 Completed Archive ({len(completed_builds)})"):
            if not completed_builds.empty:
                for _, row in completed_builds.iterrows():
                    st.write(f"✅ **{row.get('customer')}** — {row.get('date')} — {row.get('f_rim')} | {row.get('r_rim')}")
                    if st.button("Re-open Build", key=f"re_{row['id']}"):
                        base.table("builds").update(row['id'], {"status": "Building"})
                        refresh_api(); st.rerun()
            else:
                st.write("No archived builds.")

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
    
    rim_opts = sorted(df_rims['label'].tolist(), key=str.lower) if not df_rims.empty else ["Manual"]
    hub_opts = sorted(df_hubs['label'].tolist(), key=str.lower) if not df_hubs.empty else ["Manual"]

    with st.form("reg_form_v18_9_1"):
        cust = st.text_input("Customer Name")
        inv = st.text_input("Invoice URL")
        c_f, c_r = st.columns(2)
        with c_f:
            st.subheader("Front")
            fr_rim = st.selectbox("Rim", rim_opts, key="reg_fr")
            fr_hub = st.selectbox("Hub", hub_opts, key="reg_fh")
            fl_len, fr_len = st.number_input("Left (mm)", step=0.1), st.number_input("Right (mm)", step=0.1)
        with c_r:
            st.subheader("Rear")
            rr_rim = st.selectbox("Rim ", rim_opts, key="reg_rr")
            rr_hub = st.selectbox("Hub ", hub_opts, key="reg_rh")
            rl_len, rr_len = st.number_input("Left (mm) ", step=0.1), st.number_input("Right (mm) ", step=0.1)
        
        spk = st.selectbox("Spoke", sorted(df_spokes['label'].tolist()) if not df_spokes.empty else ["Std"])
        nip = st.selectbox("Nipple", sorted(df_nipples['label'].tolist()) if not df_nipples.empty else ["Std"])
        notes = st.text_area("Build Notes")
        
        if st.form_submit_button("🚀 Finalize & Register Build"):
            if cust:
                payload = {"customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", "invoice_url": inv,
                           "f_rim": fr_rim, "f_hub": fr_hub, "f_l": fl_len, "f_r": fr_len, "r_rim": rr_rim, "r_hub": rr_hub, "r_l": rl_len, "r_r": rr_len,
                           "spoke": spk, "nipple": nip, "notes": notes}
                base.table("builds").create(payload)

                # Recipe logic
                db_table = base.table("spoke_db")
                for r, h, l, rr in [(fr_rim, fr_hub, fl_len, fr_len), (rr_rim, rr_hub, rl_len, rr_len)]:
                    if r and h and l > 0:
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
        with st.form("quick_add_v18_9_1"):
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
