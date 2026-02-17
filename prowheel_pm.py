import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v17.9", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
# Ensure your secrets.toml contains:
# [airtable]
# api_key = "your_key"
# base_id = "your_base_id"
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception:
    st.error("❌ Airtable Secrets Error: Ensure keys are in Streamlit Secrets.")
    st.stop()

@st.cache_data(ttl=300)
def fetch_data(table_name, label_col):
    """Fetches data from Airtable and handles list-to-string conversion."""
    try:
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
        # Clean up Airtable lookup/link arrays
        for col in df.columns:
            df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
        return df
    except Exception:
        return pd.DataFrame()

# --- 3. ANALYTICS HELPERS ---
def get_comp_data(df, label):
    """Helper for fetching specific component specs from a dataframe."""
    if df.empty or not label: return {}
    target = str(label).strip().lower()
    df_norm = df.copy()
    df_norm['match_label'] = df_norm['label'].str.strip().str.lower()
    match = df_norm[df_norm['match_label'] == target]
    return match.iloc[0].to_dict() if not match.empty else {}

# --- 4. SESSION STATE ---
if 'build_stage' not in st.session_state:
    st.session_state.build_stage = {
        'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0,
        'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0
    }

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v17.9")
st.caption("Workshop Command Center | Streamlined Manual Intake & Library Management")

tabs = st.tabs(["🏁 Workshop", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

# --- TAB 1: WORKSHOP (PIPELINE) ---
with tabs[0]:
    c_sync1, c_sync2 = st.columns([5, 1])
    with c_sync1: st.subheader("🏁 Workshop Pipeline")
    with c_sync2:
        if st.button("🔄 Sync Data", key="global_sync", use_container_width=True):
            st.cache_data.clear(); st.toast("Synced with Airtable!"); st.rerun()
    
    df_builds = fetch_data("builds", "customer")
    df_rims = fetch_data("rims", "rim")
    df_hubs = fetch_data("hubs", "hub")
    df_spokes = fetch_data("spokes", "spoke")
    df_nipples = fetch_data("nipples", "nipple")
    
    if not df_builds.empty:
        search = st.text_input("🔍 Search Customer", key="main_search")
        f_df = df_builds[df_builds['label'].str.contains(search, case=False, na=False)] if search else df_builds
        for _, row in f_df.sort_values('id', ascending=False).iterrows():
            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')} ({row.get('date', '---')})"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**🔘 FRONT**")
                    st.write(f"**Rim:** {row.get('f_rim')}\n**Hub:** {row.get('f_hub')}")
                    st.info(f"📏 L: {row.get('f_l')} / R: {row.get('f_r')} mm")
                with c2:
                    st.markdown("**🔘 REAR**")
                    st.write(f"**Rim:** {row.get('r_rim')}\n**Hub:** {row.get('r_hub')}")
                    st.success(f"📏 L: {row.get('r_l')} / R: {row.get('r_r')} mm")
                with c3:
                    cur_stat = row.get('status', 'Order Received')
                    new_stat = st.selectbox("Status", ["Order Received", "Parts Received", "Building", "Complete"], 
                                          key=f"st_{row['id']}", 
                                          index=["Order Received", "Parts Received", "Building", "Complete"].index(cur_stat))
                    if new_stat != cur_stat:
                        base.table("builds").update(row['id'], {"status": new_stat}); st.cache_data.clear(); st.rerun()
                    
                    with st.popover("📝 Update Record Details"):
                        fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                        rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                        nt = st.text_area("Notes", value=row.get('notes', ''), key=f"nt_{row['id']}")
                        if st.button("Save Changes", key=f"btn_{row['id']}", use_container_width=True):
                            base.table("builds").update(row['id'], {"f_rim_serial": fs, "r_rim_serial": rs, "notes": nt})
                            st.cache_data.clear(); st.rerun()

# --- TAB 2: PROVEN RECIPES ---
with tabs[1]:
    st.header("📜 Proven Recipe Archive")
    df_recipes = fetch_data("spoke_db", "combo_id")
    if not df_recipes.empty:
        r_search = st.text_input("🔍 Search Recipes", key="recipe_search")
        if r_search: df_recipes = df_recipes[df_recipes['label'].str.contains(r_search, case=False, na=False)]
        st.dataframe(df_recipes[['label', 'len_l', 'len_r', 'build_count']].rename(
            columns={'label': 'Recipe', 'len_l': 'L-Len', 'len_r': 'R-Len', 'build_count': 'Builds'}
        ), use_container_width=True, hide_index=True)

# --- TAB 3: REGISTER BUILD ---
with tabs[2]:
    st.header("📝 Register New Build")
    st.link_button("⚙️ Open DT Swiss Spoke Calculator", "https://spokes-calculator.dtswiss.com/en/calculator", use_container_width=True)
    st.divider()
    
    with st.form("reg_form_v17_9"):
        cust = st.text_input("Customer Name")
        inv = st.text_input("Invoice URL")
        cf, cr = st.columns(2)
        with cf:
            st.subheader("Front Wheel")
            fr_rim = st.selectbox("Rim", df_rims['label'] if not df_rims.empty else ["Manual Entry"], key="reg_fr_rim")
            fr_hub = st.selectbox("Hub", df_hubs['label'] if not df_hubs.empty else ["Manual Entry"], key="reg_fr_hub")
            fl_len = st.number_input("Left Spoke Length (mm)", step=0.1, format="%.1f")
            fr_len = st.number_input("Right Spoke Length (mm)", step=0.1, format="%.1f")
        with cr:
            st.subheader("Rear Wheel")
            rr_rim = st.selectbox("Rim ", df_rims['label'] if not df_rims.empty else ["Manual Entry"], key="reg_rr_rim")
            rr_hub = st.selectbox("Hub ", df_hubs['label'] if not df_hubs.empty else ["Manual Entry"], key="reg_rr_hub")
            rl_len = st.number_input("Left Spoke Length (mm) ", step=0.1, format="%.1f")
            rr_len = st.number_input("Right Spoke Length (mm) ", step=0.1, format="%.1f")
        
        st.divider()
        sc1, sc2 = st.columns(2)
        spk = sc1.selectbox("Spoke Model", df_spokes['label'] if not df_spokes.empty else ["Std"])
        nip = sc2.selectbox("Nipple Model", df_nipples['label'] if not df_nipples.empty else ["Std"])
        notes = st.text_area("Journal / Build Notes")
        
        if st.form_submit_button("🚀 Finalize & Register Build"):
            if cust:
                payload = {
                    "customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), 
                    "status": "Order Received", "invoice_url": inv,
                    "f_rim": fr_rim, "f_hub": fr_hub, "f_l": fl_len, "f_r": fr_len,
                    "r_rim": rr_rim, "r_hub": rr_hub, "r_l": rl_len, "r_r": rr_len,
                    "spoke": spk, "nipple": nip, "notes": notes
                }
                base.table("builds").create(payload)
                st.cache_data.clear(); st.success("Build registered successfully!"); st.rerun()
            else: st.error("Customer name is required.")

# --- TAB 4: LIBRARY ---
with tabs[3]:
    st.header("📦 Library Management")
    
    # ➕ QUICK ADD FORM
    with st.expander("➕ Add New Component to Library"):
        cat = st.radio("Category", ["Rim", "Hub", "Spoke", "Nipple"], horizontal=True)
        with st.form("quick_add_form"):
            name = st.text_input("Component Name (Brand + Model)")
            c1, c2 = st.columns(2)
            
            p_load = {}
            if cat == "Rim":
                p_load = {
                    "rim": name, 
                    "erd": c1.number_input("ERD (mm)", step=0.1), 
                    "holes": c2.number_input("Hole Count", step=1, value=28), 
                    "weight": st.number_input("Weight (g)", step=0.1)
                }
            elif cat == "Hub":
                p_load = {
                    "hub": name, 
                    "fd_l": c1.number_input("FD Left (mm)", step=0.1), 
                    "fd_r": c2.number_input("FD Right (mm)", step=0.1),
                    "os_l": c1.number_input("Offset L (mm)", step=0.1), 
                    "os_r": c2.number_input("Offset R (mm)", step=0.1),
                    "weight": st.number_input("Weight (g)", step=0.1)
                }
            elif cat in ["Spoke", "Nipple"]:
                p_load = {cat.lower(): name, "weight": st.number_input("Unit Weight (g)", format="%.3f", step=0.001)}
            
            if st.form_submit_button(f"Save {cat} to Database"):
                if name:
                    base.table(f"{cat.lower()}s").create(p_load)
                    st.cache_data.clear(); st.success(f"{name} successfully added!"); st.rerun()
                else: st.error("Name field is required.")

    st.divider()
    
    # 🔍 LIBRARY VIEWER
    v_cat = st.radio("Inventory View:", ["rims", "hubs", "spokes", "nipples"], horizontal=True, key="lib_view_toggle")
    df_l = fetch_data(v_cat, "id")
    if not df_l.empty:
        l_search = st.text_input("🔍 Search Library Items", key="lib_search_input")
        if l_search:
            df_l = df_l[df_l.apply(lambda row: row.astype(str).str.contains(l_search, case=False).any(), axis=1)]
        st.dataframe(df_l.drop(columns=['id', 'label'], errors='ignore'), use_container_width=True, hide_index=True)
    else:
        st.info(f"No {v_cat} found in the database.")
