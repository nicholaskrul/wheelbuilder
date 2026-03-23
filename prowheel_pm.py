import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v18.7", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error(f"❌ Airtable Secrets Error: {e}")
    st.stop()

@st.cache_data(ttl=600)
def fetch_data(table_name, label_col):
    """Fetches data with a slight delay to prevent 429 rate-limiting."""
    try:
        # Rate-limiting safety: Respect Airtable's 5 req/sec limit
        time.sleep(0.25) 
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        data = []
        for rec in records:
            fields = rec['fields']
            fields['id'] = rec['id']
            if label_col in fields:
                fields['label'] = str(fields[label_col]).strip()
            data.append(fields)
        df = pd.DataFrame(data)
        # Clean up Airtable lookup/link arrays (flatten lists to strings)
        for col in df.columns:
            df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
        return df
    except Exception as e:
        st.sidebar.error(f"Error fetching '{table_name}': {e}")
        return pd.DataFrame()

# --- 3. ANALYTICS HELPERS ---
def get_comp_data(df, label):
    """Retrieves component dictionary from label string."""
    if df.empty or not label: return {}
    target = str(label).strip().lower()
    df_norm = df.copy()
    df_norm['match_label'] = df_norm['label'].str.strip().str.lower()
    match = df_norm[df_norm['match_label'] == target]
    return match.iloc[0].to_dict() if not match.empty else {}

# --- 4. SESSION STATE ---
# Flattened session state structure to prevent AttributeErrors
if 'build_stage' not in st.session_state:
    st.session_state.build_stage = {
        'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0,
        'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0
    }

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v18.7")
st.caption("Workshop Command Center | Optimized API Logic & Visual Tracking")

tabs = st.tabs(["🏁 Workshop", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

# --- TAB 1: WORKSHOP (PIPELINE) ---
with tabs[0]:
    c_sync1, c_sync2 = st.columns([5, 1])
    with c_sync1: st.subheader("🏁 Workshop Pipeline")
    with c_sync2:
        if st.button("🔄 Sync", key="global_sync", use_container_width=True):
            st.cache_data.clear(); st.toast("Refreshing Data..."); st.rerun()
    
    df_builds = fetch_data("builds", "customer")
    df_rims = fetch_data("rims", "rim")
    df_hubs = fetch_data("hubs", "hub")
    df_spokes = fetch_data("spokes", "spoke")
    df_nipples = fetch_data("nipples", "nipple")
    
    if not df_builds.empty:
        # Resilient bucketing for Active vs Complete builds
        active_mask = df_builds['status'].fillna("Order Received") != "Complete"
        active_builds = df_builds[active_mask].sort_values('id', ascending=False)
        completed_builds = df_builds[~active_mask].sort_values('id', ascending=False)

        # 📊 Status Metrics Summary
        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("Active Jobs", len(active_builds))
        c_m2.metric("In Progress", len(active_builds[active_builds['status'] == "Building"]))
        c_m3.metric("Archived", len(completed_builds))

        search = st.text_input("🔍 Search Active Customers", key="main_search")
        if search:
            active_builds = active_builds[active_builds['label'].str.contains(search, case=False, na=False)]

        st.write("### 🛠️ On the Bench")
        for _, row in active_builds.iterrows():
            # Get Hardware Weights for the specific build
            spk_data = get_comp_data(df_spokes, row.get('spoke'))
            nip_data = get_comp_data(df_nipples, row.get('nipple'))
            u_spk, u_nip = float(spk_data.get('weight', 0)), float(nip_data.get('weight', 0))

            f_res = {"total": 0.0, "exists": False}
            if row.get('f_rim'):
                frd, fhd = get_comp_data(df_rims, row.get('f_rim')), get_comp_data(df_hubs, row.get('f_hub'))
                h = int(frd.get('holes', 0))
                f_res.update({"exists": True, "rim_w": float(frd.get('weight', 0)), "hub_w": float(fhd.get('weight', 0))})
                f_res["total"] = f_res["rim_w"] + f_res["hub_w"] + (h * u_spk) + (h * u_nip)

            r_res = {"total": 0.0, "exists": False}
            if row.get('r_rim'):
                rrd, rhd = get_comp_data(df_rims, row.get('r_rim')), get_comp_data(df_hubs, row.get('r_hub'))
                h = int(rrd.get('holes', 0))
                r_res.update({"exists": True, "rim_w": float(rrd.get('weight', 0)), "hub_w": float(rhd.get('weight', 0))})
                r_res["total"] = r_res["rim_w"] + r_res["hub_w"] + (h * u_spk) + (h * u_nip)

            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')} ({row.get('date', '---')})"):
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
                    new = st.selectbox("Status", opts, index=opts.index(cur) if cur in opts else 0, key=f"s_{row['id']}")
                    if new != cur:
                        base.table("builds").update(row['id'], {"status": new}); st.cache_data.clear(); st.rerun()
                    
                    with st.popover("📝 Details / Serial #"):
                        fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                        rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                        nt = st.text_area("Notes", value=row.get('notes', ''), key=f"nt_{row['id']}")
                        if st.button("Save", key=f"btn_{row['id']}", use_container_width=True):
                            base.table("builds").update(row['id'], {"f_rim_serial": fs, "r_rim_serial": rs, "notes": nt}); st.cache_data.clear(); st.rerun()

        # --- COMPLETED ARCHIVE ---
        st.divider()
        with st.expander(f"📁 Completed Archive ({len(completed_builds)})"):
            if not completed_builds.empty:
                for _, row in completed_builds.iterrows():
                    st.write(f"✅ **{row.get('customer')}** — {row.get('f_rim')} | {row.get('r_rim')}")
                    if st.button("Re-open Build", key=f"re_{row['id']}"):
                        base.table("builds").update(row['id'], {"status": "Building"}); st.cache_data.clear(); st.rerun()

# --- TAB 2: PROVEN RECIPES ---
with tabs[1]:
    st.header("📜 Proven Recipe Archive")
    df_recipes = fetch_data("spoke_db", "combo_id")
    if not df_recipes.empty:
        r_search = st.text_input("🔍 Search Recipes", key="recipe_search")
        if r_search: df_recipes = df_recipes[df_recipes['label'].str.contains(r_search, case=False, na=False)]
        # Alphabetical sorting for recipe list
        df_recipes = df_recipes.sort_values('label', key=lambda x: x.str.lower())
        st.dataframe(df_recipes[['label', 'len_l', 'len_r', 'build_count']].rename(columns={'label': 'Recipe', 'len_l': 'L-Len', 'len_r': 'R-Len', 'build_count': 'Hits'}), use_container_width=True, hide_index=True)

# --- TAB 3: REGISTER BUILD ---
with tabs[2]:
    st.header("📝 Register New Build")
    st.link_button("⚙️ Open DT Swiss Spoke Calculator", "https://spokes-calculator.dtswiss.com/en/calculator", use_container_width=True)
    st.divider()
    
    # Pre-sorted lists for dropdowns
    rim_list = sorted(df_rims['label'].tolist(), key=str.lower) if not df_rims.empty else ["Manual"]
    hub_list = sorted(df_hubs['label'].tolist(), key=str.lower) if not df_hubs.empty else ["Manual"]
    spoke_list = sorted(df_spokes['label'].tolist(), key=str.lower) if not df_spokes.empty else ["Std"]
    nipple_list = sorted(df_nipples['label'].tolist(), key=str.lower) if not df_nipples.empty else ["Std"]

    with st.form("reg_form_v18_7"):
        cust = st.text_input("Customer Name")
        inv = st.text_input("Invoice URL")
        cf, cr = st.columns(2)
        with cf:
            st.subheader("Front")
            fr_rim = st.selectbox("Rim", rim_list, key="reg_fr_rim")
            fr_hub = st.selectbox("Hub", hub_list, key="reg_fr_hub")
            fl_len, fr_len = st.number_input("Left Spoke (mm)", step=0.1, format="%.1f"), st.number_input("Right Spoke (mm)", step=0.1, format="%.1f")
        with cr:
            st.subheader("Rear")
            rr_rim = st.selectbox("Rim ", rim_list, key="reg_rr_rim")
            rr_hub = st.selectbox("Hub ", hub_list, key="reg_rr_hub")
            rl_len, rr_len = st.number_input("Left Spoke (mm) ", step=0.1, format="%.1f"), st.number_input("Right Spoke (mm) ", step=0.1, format="%.1f")
        
        st.divider()
        sc1, sc2 = st.columns(2)
        spk = sc1.selectbox("Spoke", spoke_list)
        nip = sc2.selectbox("Nipple", nipple_list)
        notes = st.text_area("Build Notes")
        
        if st.form_submit_button("🚀 Finalize & Register Build"):
            if cust:
                # 1. Main Table creation
                payload = {"customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", "invoice_url": inv,
                           "f_rim": fr_rim, "f_hub": fr_hub, "f_l": fl_len, "f_r": fr_len, "r_rim": rr_rim, "r_hub": rr_hub, "r_l": rl_len, "r_r": rr_len,
                           "spoke": spk, "nipple": nip, "notes": notes}
                base.table("builds").create(payload)

                # 2. Recipe Archiving (Fixed Syntax with quote escaping)
                db_table = base.table("spoke_db")
                for rim, hub, l, r in [(fr_rim, fr_hub, fl_len, fr_len), (rr_rim, rr_hub, rl_len, rr_len)]:
                    if rim and hub and l > 0:
                        rd_id, hd_id = df_rims[df_rims['label'] == rim]['id'].values[0], df_hubs[df_hubs['label'] == hub]['id'].values[0]
                        fingerprint = f"{rim} | {hub}"
                        clean_fp = fingerprint.replace("'", "\\'")
                        formula = f"{{combo_id}}='{clean_fp}'"
                        
                        exist = db_table.all(formula=formula)
                        if exist:
                            hits = exist[0]['fields'].get('build_count', 1)
                            db_table.update(exist[0]['id'], {"build_count": hits + 1, "len_l": l, "len_r": r})
                        else:
                            db_table.create({"rim": [rd_id], "hub": [hd_id], "len_l": l, "len_r": r, "build_count": 1})
                
                st.cache_data.clear(); st.success("Registered and Recipe Archived!"); st.rerun()

# --- TAB 4: LIBRARY ---
with tabs[3]:
    st.header("📦 Library Management")
    with st.expander("➕ Add Component"):
        cat = st.radio("Category", ["Rim", "Hub", "Spoke", "Nipple"], horizontal=True)
        with st.form("quick_add_v18_7"):
            name = st.text_input("Name")
            c1, c2 = st.columns(2)
            p = {}
            if cat == "Rim": p = {"rim": name, "erd": c1.number_input("ERD", step=0.1), "holes": c2.number_input("Holes", step=1), "weight": st.number_input("Weight")}
            elif cat == "Hub": p = {"hub": name, "fd_l": c1.number_input("FD-L"), "fd_r": c2.number_input("FD-R"), "os_l": c1.number_input("OS-L"), "os_r": c2.number_input("OS-R"), "weight": st.number_input("Weight")}
            elif cat in ["Spoke", "Nipple"]: p = {cat.lower(): name, "weight": st.number_input("Weight (g)", format="%.3f")}
            if st.form_submit_button("Save to Library"):
                if name: base.table(f"{cat.lower()}s").create(p); st.cache_data.clear(); st.rerun()
    
    v_cat = st.radio("View Inventory:", ["rims", "hubs", "spokes", "nipples"], horizontal=True, key="lib_view")
    df_l = fetch_data(v_cat, "id")
    if not df_l.empty:
        # Sort library view alphabetically
        df_l = df_l.sort_values('label', key=lambda x: x.str.lower())
        st.dataframe(df_l.drop(columns=['id', 'label'], errors='ignore'), use_container_width=True, hide_index=True)
