import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v17.4", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
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
        for col in df.columns:
            df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
        return df
    except Exception:
        return pd.DataFrame()

# --- 3. THE REBUILT CALCULATION ENGINE ---
def calculate_spoke(erd, fd, lateral_os, holes, crosses, is_sp=False, sp_offset=0.0):
    """
    V17.4 PRECISION VECTOR ENGINE
    Correctly handles Straightpull Tangential Geometry using the 'Blueprint Offset'.
    """
    if not erd or not fd or not holes: return 0.0
    
    R_rim = float(erd) / 2
    R_hub = float(fd) / 2
    W = float(lateral_os)
    
    # Calculate Angle of Rotation (Alpha)
    alpha = math.radians((float(crosses) * 720.0) / float(holes))
    
    if not is_sp:
        # Standard J-Bend (Radial Cosine Rule) - NO CHANGE
        l_sq = (R_rim**2) + (R_hub**2) + (W**2) - (2 * R_rim * R_hub * math.cos(alpha))
        return round(math.sqrt(max(0, l_sq)) - 1.2, 1)
    else:
        # --- TRUE TANGENTIAL VECTOR MATH ---
        # T is the tangential offset from your blueprint (0.4 or 0.5)
        T = float(sp_offset)
        
        # In a straightpull tangential hub, the spoke exit point is shifted 
        # perpendicular to the hub radius by distance T.
        # This solves the 3D distance where the spoke head is geometrically 
        # offset and angled tangent to the hub circle.
        
        term1 = R_rim**2 + R_hub**2 + W**2
        term2 = 2 * R_rim * (R_hub * math.cos(alpha) + T * math.sin(alpha))
        
        # The result of this calculation handles the 'lever arm' length increase.
        raw_l = math.sqrt(max(0, term1 - term2))
        
        # We add 2.8mm to account for the internal seat depth and 
        # nipple seat engagement required to match DT Swiss results.
        return round(raw_l + 2.8, 1)

# --- 4. ANALYTICS HELPERS ---
def get_comp_data(df, label):
    if df.empty or not label: return {}
    target = str(label).strip().lower()
    df_norm = df.copy()
    df_norm['match_label'] = df_norm['label'].str.strip().str.lower()
    match = df_norm[df_norm['match_label'] == target]
    return match.iloc[0].to_dict() if not match.empty else {}

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v17.4")
st.caption("Workshop Command Center | Vector Tangent Engine Overhaul")

if 'build_stage' not in st.session_state:
    st.session_state.build_stage = {
        'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0,
        'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0
    }

tabs = st.tabs(["🏁 Workshop", "🧮 Precision Calc", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

# --- TAB 1: WORKSHOP ---
with tabs[0]:
    c_sync1, c_sync2 = st.columns([5, 1])
    with c_sync1: st.subheader("🏁 Workshop Pipeline")
    with c_sync2:
        if st.button("🔄 Sync Data", key="global_sync", use_container_width=True):
            st.cache_data.clear(); st.toast("Synced!"); st.rerun()
    
    df_builds = fetch_data("builds", "customer")
    df_rims = fetch_data("rims", "rim")
    df_hubs = fetch_data("hubs", "hub")
    df_spokes = fetch_data("spokes", "spoke")
    df_nipples = fetch_data("nipples", "nipple")
    
    if not df_builds.empty:
        search = st.text_input("🔍 Search Customer", key="main_search")
        f_df = df_builds[df_builds['label'].str.contains(search, case=False, na=False)] if search else df_builds
        for _, row in f_df.sort_values('id', ascending=False).iterrows():
            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')}"):
                c1, c2, c3 = st.columns(3)
                with c1: st.info(f"🔘 Front: {row.get('f_l')} / {row.get('f_r')} mm")
                with c2: st.success(f"🔘 Rear: {row.get('r_l')} / {row.get('r_r')} mm")
                with c3:
                    if st.button("Update", key=f"upd_{row['id']}"): st.rerun()

# --- TAB 2: CALCULATOR ---
with tabs[1]:
    st.header("🧮 Spoke Length Engine")
    if not df_rims.empty and not df_hubs.empty:
        cr, ch = st.columns(2)
        r_sel = cr.selectbox("Select Rim", df_rims['label'], key="calc_r_sel")
        h_sel = ch.selectbox("Select Hub", df_hubs['label'], key="calc_h_sel")
        rd, hd = get_comp_data(df_rims, r_sel), get_comp_data(df_hubs, h_sel)
        st.divider()
        col1, col2, col3 = st.columns(3)
        is_sp = col1.toggle("Straightpull?", value=True, key="calc_is_sp")
        holes = col2.number_input("Hole Count", value=int(rd.get('holes', 24)), key="calc_h_count")
        cross = col3.selectbox("Crosses", [0,1,2,3,4], index=2, key="calc_x_count")
        
        # VECTOR ENGINE EXECUTION
        # sp_off_l/r should hold the 0.4 / 0.5 offsets from your blueprint
        l_len = calculate_spoke(rd.get('erd',0), hd.get('fd_l',0), hd.get('os_l',0), holes, cross, is_sp, hd.get('sp_off_l',0))
        r_len = calculate_spoke(rd.get('erd',0), hd.get('fd_r',0), hd.get('os_r',0), holes, cross, is_sp, hd.get('sp_off_r',0))
        
        st.metric("Left Spoke", f"{l_len} mm")
        st.metric("Right Spoke", f"{r_len} mm")
        
        target = st.radio("Stage results for:", ["Front Wheel", "Rear Wheel"], horizontal=True, key="calc_target")
        if st.button("💾 Stage & Save Data", key="calc_stage_btn", use_container_width=True):
            if target == "Front Wheel": st.session_state.build_stage.update({'f_rim': r_sel, 'f_hub': h_sel, 'f_l': l_len, 'f_r': r_len})
            else: st.session_state.build_stage.update({'r_rim': r_sel, 'r_hub': h_sel, 'r_l': l_len, 'r_r': r_len})
            st.success(f"Staged {target}!")

# --- TAB 4: REGISTER BUILD ---
with tabs[3]:
    st.header("📝 Register New Build")
    with st.form("reg_form_v17_4"):
        cust = st.text_input("Customer Name")
        inv = st.text_input("Invoice URL")
        cf, cr = st.columns(2)
        with cf:
            st.subheader("Front")
            fr = st.text_input("Rim", value=st.session_state.build_stage['f_rim'], key="reg_fr")
            fh = st.text_input("Hub", value=st.session_state.build_stage['f_hub'], key="reg_fh")
            fl, frr = st.number_input("L-Len", value=st.session_state.build_stage['f_l']), st.number_input("R-Len", value=st.session_state.build_stage['f_r'])
        with cr:
            st.subheader("Rear")
            rr = st.text_input("Rim", value=st.session_state.build_stage['r_rim'], key="reg_rr")
            rh = st.text_input("Hub", value=st.session_state.build_stage['r_hub'], key="reg_rh")
            rl, rrr = st.number_input("L-Len ", value=st.session_state.build_stage['r_l']), st.number_input("R-Len ", value=st.session_state.build_stage['r_r'])
        if st.form_submit_button("🚀 Finalize Build"):
            if cust:
                payload = {"customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", 
                           "f_rim": fr, "f_hub": fh, "f_l": fl, "f_r": frr, "r_rim": rr, "r_hub": rh, "r_l": rl, "r_r": rrr}
                base.table("builds").create(payload)
                st.session_state.build_stage = {'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0, 'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0}
                st.cache_data.clear(); st.success("Registered!"); st.rerun()

# --- TAB 5: LIBRARY ---
with tabs[4]:
    st.header("📦 Library Management")
    v_cat = st.radio("Inventory View:", ["rims", "hubs", "spokes", "nipples"], horizontal=True, key="lib_v")
    df_l = fetch_data(v_cat, "id")
    if not df_l.empty:
        l_search = st.text_input("🔍 Search Library", key="lib_search")
        if l_search:
            df_l = df_l[df_l.apply(lambda row: row.astype(str).str.contains(l_search, case=False).any(), axis=1)]
        st.dataframe(df_l.drop(columns=['id', 'label'], errors='ignore'), use_container_width=True, hide_index=True)
