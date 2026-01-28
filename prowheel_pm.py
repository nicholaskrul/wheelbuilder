import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v12.2", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("Missing Airtable Secrets in Streamlit Cloud Settings.")
    st.stop()

@st.cache_data(ttl=600)
def get_table(table_name):
    """Fetches records from Airtable with robust error handling for 403/404 errors."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records:
            return pd.DataFrame()
        data = [ {**rec['fields'], 'id': rec['id']} for rec in records ]
        return pd.DataFrame(data)
    except Exception as e:
        st.warning(f"⚠️ Table '{table_name}' not accessible. Check Airtable permissions/names. Error: {e}")
        return pd.DataFrame()

# --- 3. CALCULATION ENGINE (v11.5) ---
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, hole_diam=2.4, round_mode="None"):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    alpha_rad = math.radians((float(crosses) * 720.0) / float(holes))
    if not is_sp:
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, l_sq)) - (float(hole_diam) / 2)
    else:
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_offset)
    if round_mode == "Nearest Even": return float(round(length / 2) * 2)
    elif round_mode == "Nearest Odd": return float(round((length - 1) / 2) * 2 + 1)
    return round(length, 1)

# --- 4. SESSION STATE ---
if 'f_l' not in st.session_state:
    for key in ['f_l', 'f_r', 'r_l', 'r_r']: st.session_state[key] = 0.0

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab")
st.caption("v12.2 | Airtable Stable")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "📦 Inventory", "➕ Register Build", "📄 Spec Sheet"])

# --- DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    df_builds = get_table("builds")
    if not df_builds.empty:
        for _, row in df_builds.iterrows():
            st.write(f"**{row.get('customer', 'Unknown')}** | Status: `{row.get('status', 'N/A')}`")
            st.divider()
    else: st.info("No active builds found in Airtable.")

# --- CALCULATOR ---
with tabs[1]:
    st.header("🧮 Spoke Calculator")
    df_rims, df_hubs = get_table("rims"), get_table("hubs")
    if not df_rims.empty and not df_hubs.empty:
        c1, c2 = st.columns(2)
        rim_sel = c1.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
        hub_sel = c2.selectbox("Select Hub", df_hubs['brand'] + " " + df_hubs['model'])
        r_dat = df_rims[df_rims['brand'] + " " + df_rims['model'] == rim_sel].iloc[0]
        h_dat = df_hubs[df_hubs['brand'] + " " + df_hubs['model'] == hub_sel].iloc[0]
        i1, i2, i3 = st.columns(3)
        holes = i1.number_input("Spoke Count", value=int(r_dat['holes']), step=2)
        l_cross = i2.selectbox("L-Cross", [0,1,2,3,4], index=3)
        r_cross = i3.selectbox("R-Cross", [0,1,2,3,4], index=3)
        is_sp = st.toggle("Straightpull Hub?", value=True)
        res_l = calculate_precision_spoke(r_dat['erd'], h_dat['fd_l'], h_dat['os_l'], holes, l_cross, is_sp, h_dat.get('sp_off_l', 0))
        res_r = calculate_precision_spoke(r_dat['erd'], h_dat['fd_r'], h_dat['os_r'], holes, r_cross, is_sp, h_dat.get('sp_off_r', 0))
        st.metric("L Length", f"{res_l} mm"); st.metric("R Length", f"{res_r} mm")
        if st.button("Apply and Stage"):
            st.session_state.f_l, st.session_state.f_r = res_l, res_r
            st.success("Staged!")

# --- INVENTORY ---
with tabs[3]:
    st.header("📦 Spoke Inventory")
    df_inv = get_table("spoke_inventory")
    if not df_inv.empty:
        st.dataframe(df_inv[['brand', 'model', 'length', 'stock']], use_container_width=True)

# --- REGISTER BUILD ---
with tabs[4]:
    st.header("📝 Register Build")
    df_rims, df_hubs, df_spk = get_table("rims"), get_table("hubs"), get_table("spokes")
    if not df_rims.empty:
        with st.form("new_build"):
            cust = st.text_input("Customer Name")
            f_r = st.selectbox("Front Rim", df_rims['brand'] + " " + df_rims['model'])
            f_h = st.selectbox("Front Hub", df_hubs['brand'] + " " + df_hubs['model'])
            spk_mod = st.selectbox("Spoke Model", df_spk['brand'] + " " + df_spk['model'])
            col1, col2 = st.columns(2)
            vfl = col1.number_input("F-L", value=st.session_state.f_l)
            vfr = col2.number_input("F-R", value=st.session_state.f_r)
            if st.form_submit_button("🚀 Finalize Build"):
                base.table("builds").create({"customer": cust, "f_rim": f_r, "f_hub": f_h, "spoke": spk_mod, "f_l": vfl, "f_r": vfr, "date": datetime.now().strftime("%Y-%m-%d")})
                st.cache_data.clear(); st.success("Build registered!"); st.rerun()

# --- SPEC SHEET ---
with tabs[5]:
    st.header("📄 Spec Sheet")
    df_b = get_table("builds")
    if not df_b.empty:
        sel_cust = st.selectbox("Project", df_b['customer'])
        b = df_b[df_b['customer'] == sel_cust].iloc[0]
        st.write(f"### Build for: {sel_cust}")
        st.info(f"Front: L {b.get('f_l')} / R {b.get('f_r')} mm")
