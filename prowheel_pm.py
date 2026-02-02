import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v15.0", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Airtable Secrets Error: Ensure secrets are configured.")
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
    except:
        return pd.DataFrame()

# --- 3. ANALYTICS HELPERS ---
def get_comp_data(df, label):
    if df.empty or not label: return {}
    target = str(label).strip().lower()
    df_norm = df.copy()
    df_norm['match_label'] = df_norm['label'].str.strip().str.lower()
    match = df_norm[df_norm['match_label'] == target]
    return match.iloc[0].to_dict() if not match.empty else {}

def calculate_spoke(erd, fd, os, holes, crosses, is_sp=False, sp_off=0.0):
    if not erd or not fd or not holes: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    angle_rad = math.radians((float(crosses) * 720.0) / float(holes))
    if not is_sp:
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        return round(math.sqrt(max(0, l_sq)) - 1.2, 1)
    else:
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_off)
        return round(length, 1)

# --- 4. SESSION STATE ---
if 'build_stage' not in st.session_state:
    st.session_state.build_stage = {
        'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0,
        'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0
    }

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v15.0")
st.caption("Enhanced Workshop Suite | Dashboard + Specs Unified")

tabs = st.tabs(["🏁 Workshop", "🧮 Precision Calc", "➕ Register Build", "📦 Library"])

# --- TAB 1: UNIFIED WORKSHOP (Dashboard + Spec Sheet) ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline & Specifications")
    
    # Fetch all necessary data
    df_builds = fetch_data("builds", "customer")
    df_rims = fetch_data("rims", "rim")
    df_hubs = fetch_data("hubs", "hub")
    df_spokes = fetch_data("spokes", "spoke")
    df_nipples = fetch_data("nipples", "nipple")
    
    if not df_builds.empty:
        search = st.text_input("🔍 Search Customer")
        f_df = df_builds[df_builds['label'].str.contains(search, case=False, na=False)] if search else df_builds
        
        for _, row in f_df.sort_values('id', ascending=False).iterrows():
            # Calculate weights for header
            tw = 0.0
            spoke_weight = float(get_comp_data(df_spokes, row.get('spoke')).get('weight', 0))
            nipple_weight = float(get_comp_data(df_nipples, row.get('nipple')).get('weight', 0))
            
            # Build header with total weight
            if row.get('f_rim') or row.get('r_rim'):
                front_weight = 0.0
                rear_weight = 0.0
                
                if row.get('f_rim'):
                    f_rim_data = get_comp_data(df_rims, row.get('f_rim'))
                    f_hub_data = get_comp_data(df_hubs, row.get('f_hub'))
                    # Only calculate if we actually got rim data back
                    if f_rim_data:
                        f_rim_weight = float(f_rim_data.get('weight', 0))
                        f_hub_weight = float(f_hub_data.get('weight', 0))
                        f_hole_count = int(f_rim_data.get('holes', 28))
                        front_weight = f_rim_weight + f_hub_weight + (f_hole_count * (spoke_weight + nipple_weight))
                        tw += front_weight
                
                if row.get('r_rim'):
                    r_rim_data = get_comp_data(df_rims, row.get('r_rim'))
                    r_hub_data = get_comp_data(df_hubs, row.get('r_hub'))
                    # Only calculate if we actually got rim data back
                    if r_rim_data:
                        r_rim_weight = float(r_rim_data.get('weight', 0))
                        r_hub_weight = float(r_hub_data.get('weight', 0))
                        r_hole_count = int(r_rim_data.get('holes', 28))
                        rear_weight = r_rim_weight + r_hub_weight + (r_hole_count * (spoke_weight + nipple_weight))
                        tw += rear_weight
                
                weight_display = f" | ⚖️ {int(tw)}g total"
            else:
                weight_display = ""
            
            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')} ({row.get('date')}){weight_display}"):
                # Top section: Status and Invoice
                top_col1, top_col2 = st.columns([3, 1])
                
                with top_col1:
                    current_status = row.get('status', 'Order Received')
                    new_stat = st.selectbox("Status", 
                                          ["Order Received", "Parts Received", "Building", "Complete"], 
                                          key=f"stat_{row['id']}", 
                                          index=["Order Received", "Parts Received", "Building", "Complete"].index(current_status))
                    if new_stat != current_status:
                        base.table("builds").update(row['id'], {"status": new_stat})
                        st.rerun()
                
                with top_col2:
                    if row.get('invoice_url'):
                        st.link_button("📄 Invoice", row['invoice_url'], use_container_width=True)
                
                st.divider()
                
                # Main build details
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.markdown("**🔘 FRONT WHEEL**")
                    if row.get('f_rim'):
                        st.write(f"**Rim:** {row.get('f_rim')}")
                        st.write(f"**Hub:** {row.get('f_hub')}")
                        st.write(f"**Spoke:** {row.get('spoke', 'N/A')}")
                        st.write(f"**Nipple:** {row.get('nipple', 'N/A')}")
                        st.write(f"**Serial:** `{row.get('f_rim_serial', 'NONE')}`")
                        st.info(f"📏 **Spoke Lengths**\nLeft: {row.get('f_l')} mm\nRight: {row.get('f_r')} mm")
                        
                        # Weight breakdown
                        if row.get('f_rim'):
                            f_rim_data = get_comp_data(df_rims, row.get('f_rim'))
                            f_hub_data = get_comp_data(df_hubs, row.get('f_hub'))
                            f_rim_weight = float(f_rim_data.get('weight', 0))
                            f_hub_weight = float(f_hub_data.get('weight', 0))
                            f_hole_count = int(f_rim_data.get('holes', 28))
                            f_spoke_total = f_hole_count * spoke_weight
                            f_nipple_total = f_hole_count * nipple_weight
                            front_total = f_rim_weight + f_hub_weight + f_spoke_total + f_nipple_total
                            
                            st.markdown("**Weight Breakdown:**")
                            st.write(f"• Rim: {int(f_rim_weight)}g")
                            st.write(f"• Hub: {int(f_hub_weight)}g")
                            st.write(f"• Spokes: {int(f_spoke_total)}g")
                            st.write(f"• Nipples: {int(f_nipple_total)}g")
                            st.metric("Front Total", f"{int(front_total)}g")
                    else:
                        st.info("No front wheel specified")
                
                with c2:
                    st.markdown("**🔘 REAR WHEEL**")
                    if row.get('r_rim'):
                        st.write(f"**Rim:** {row.get('r_rim')}")
                        st.write(f"**Hub:** {row.get('r_hub')}")
                        st.write(f"**Spoke:** {row.get('spoke', 'N/A')}")
                        st.write(f"**Nipple:** {row.get('nipple', 'N/A')}")
                        st.write(f"**Serial:** `{row.get('r_rim_serial', 'NONE')}`")
                        st.success(f"📏 **Spoke Lengths**\nLeft: {row.get('r_l')} mm\nRight: {row.get('r_r')} mm")
                        
                        # Weight breakdown
                        if row.get('r_rim'):
                            r_rim_data = get_comp_data(df_rims, row.get('r_rim'))
                            r_hub_data = get_comp_data(df_hubs, row.get('r_hub'))
                            r_rim_weight = float(r_rim_data.get('weight', 0))
                            r_hub_weight = float(r_hub_data.get('weight', 0))
                            r_hole_count = int(r_rim_data.get('holes', 28))
                            r_spoke_total = r_hole_count * spoke_weight
                            r_nipple_total = r_hole_count * nipple_weight
                            rear_total = r_rim_weight + r_hub_weight + r_spoke_total + r_nipple_total
                            
                            st.markdown("**Weight Breakdown:**")
                            st.write(f"• Rim: {int(r_rim_weight)}g")
                            st.write(f"• Hub: {int(r_hub_weight)}g")
                            st.write(f"• Spokes: {int(r_spoke_total)}g")
                            st.write(f"• Nipples: {int(r_nipple_total)}g")
                            st.metric("Rear Total", f"{int(rear_total)}g")
                    else:
                        st.info("No rear wheel specified")
                
                with c3:
                    st.markdown("**⚙️ ACTIONS**")
                    
                    # Serial number management
                    if current_status in ["Parts Received", "Building", "Complete"]:
                        with st.popover("📝 Edit Rim Serials"):
                            fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                            rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                            if st.button("Save Serials", key=f"btn_{row['id']}"):
                                base.table("builds").update(row['id'], {"f_rim_serial": fs, "r_rim_serial": rs})
                                st.rerun()
                    
                    # Total weight display
                    if tw > 0:
                        st.divider()
                        st.metric("**WHEELSET WEIGHT**", f"{int(tw)}g", delta=None)
                    
                    # Notes display
                    if row.get('notes'):
                        st.divider()
                        st.markdown("**📋 Notes:**")
                        st.write(row.get('notes'))
    else:
        st.info("Pipeline empty. Register your first build to get started!")

# --- TAB 2: CALCULATOR ---
with tabs[1]:
    st.header("🧮 Spoke Length Engine")
    df_rims, df_hubs = fetch_data("rims", "rim"), fetch_data("hubs", "hub")
    if not df_rims.empty and not df_hubs.empty:
        cr, ch = st.columns(2)
        r_sel = cr.selectbox("Select Rim", df_rims['label'])
        h_sel = ch.selectbox("Select Hub", df_hubs['label'])
        rd, hd = get_comp_data(df_rims, r_sel), get_comp_data(df_hubs, h_sel)
        st.divider()
        col1, col2, col3 = st.columns(3)
        is_sp = col1.toggle("Straightpull?", value=True, key="calc_is_sp")
        holes = col2.number_input("Hole Count", value=int(rd.get('holes', 28)), key="calc_holes")
        cross = col3.selectbox("Crosses", [0,1,2,3,4], index=3, key="calc_cross")
        l_len = calculate_spoke(rd.get('erd',0), hd.get('fd_l',0), hd.get('os_l',0), holes, cross, is_sp, hd.get('sp_off_l',0))
        r_len = calculate_spoke(rd.get('erd',0), hd.get('fd_r',0), hd.get('os_r',0), holes, cross, is_sp, hd.get('sp_off_r',0))
        st.metric("Left Spoke", f"{l_len} mm")
        st.metric("Right Spoke", f"{r_len} mm")
        target = st.radio("Stage results for:", ["Front Wheel", "Rear Wheel"], horizontal=True, key="calc_target")
        if st.button("💾 Stage Component Data", key="calc_stage_btn"):
            if target == "Front Wheel":
                st.session_state.build_stage.update({'f_rim': r_sel, 'f_hub': h_sel, 'f_l': l_len, 'f_r': r_len})
            else:
                st.session_state.build_stage.update({'r_rim': r_sel, 'r_hub': h_sel, 'r_l': l_len, 'r_r': r_len})
            st.success(f"Staged {target}!")

# --- TAB 3: REGISTER BUILD ---
with tabs[2]:
    st.header("📝 Register New Build")
    df_spk, df_nip = fetch_data("spokes", "spoke"), fetch_data("nipples", "nipple")
    build_type = st.radio("Config:", ["Full Wheelset", "Front Only", "Rear Only"], horizontal=True, key="reg_type")
    with st.form("reg_form_v15"):
        cust = st.text_input("Customer Name")
        inv = st.text_input("Invoice URL")
        payload = {"customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", "invoice_url": inv}
        cf, cr = st.columns(2)
        if build_type in ["Full Wheelset", "Front Only"]:
            with cf:
                st.subheader("Front")
                fr = st.text_input("Rim", value=st.session_state.build_stage['f_rim'], key="reg_f_rim")
                fh = st.text_input("Hub", value=st.session_state.build_stage['f_hub'], key="reg_f_hub")
                fl = st.number_input("L-Len", value=st.session_state.build_stage['f_l'], key="reg_f_l")
                frr = st.number_input("R-Len", value=st.session_state.build_stage['f_r'], key="reg_f_r")
                payload.update({"f_rim": fr, "f_hub": fh, "f_l": fl, "f_r": frr})
        if build_type in ["Full Wheelset", "Rear Only"]:
            with cr:
                st.subheader("Rear")
                rr = st.text_input("Rim", value=st.session_state.build_stage['r_rim'], key="reg_r_rim")
                rh = st.text_input("Hub", value=st.session_state.build_stage['r_hub'], key="reg_r_hub")
                rl = st.number_input("L-Len", value=st.session_state.build_stage['r_l'], key="reg_r_l")
                rrr = st.number_input("R-Len", value=st.session_state.build_stage['r_r'], key="reg_r_r")
                payload.update({"r_rim": rr, "r_hub": rh, "r_l": rl, "r_r": rrr})
        sc1, sc2 = st.columns(2)
        payload.update({"spoke": sc1.selectbox("Spoke", df_spk['label'] if not df_spk.empty else ["Standard"], key="reg_spk"),
                        "nipple": sc2.selectbox("Nipple", df_nip['label'] if not df_nip.empty else ["Standard"], key="reg_nip"),
                        "notes": st.text_area("Notes", key="reg_notes")})
        if st.form_submit_button("🚀 Finalize Build"):
            base.table("builds").create(payload)
            st.session_state.build_stage = {'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0, 'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0}
            st.cache_data.clear()
            st.success("Registered!")
            st.rerun()

# --- TAB 4: LIBRARY ---
with tabs[3]:
    st.header("📦 Library Management")
    with st.expander("➕ Add New Component", expanded=False):
        cat = st.radio("Category", ["Rim", "Hub", "Spoke", "Nipple"], horizontal=True, key="lib_cat")
        with st.form("lib_add_form"):
            name = st.text_input(f"New {cat} Name", key="lib_name")
            c1, c2 = st.columns(2)
            lib_payload = {}
            if cat == "Rim":
                lib_payload = {"rim": name, "erd": c1.number_input("ERD (mm)", step=0.1, key="lib_rim_erd"), 
                               "holes": c2.number_input("Hole Count", step=1, value=28, key="lib_rim_holes"), 
                               "weight": st.number_input("Weight (g)", step=0.1, key="lib_rim_w")}
            elif cat == "Hub":
                lib_payload = {"hub": name, "fd_l": c1.number_input("FD Left", step=0.1, key="lib_h_fdl"), 
                               "fd_r": c2.number_input("FD Right", step=0.1, key="lib_h_fdr"), 
                               "os_l": c1.number_input("Offset Left", step=0.1, key="lib_h_osl"), 
                               "os_r": c2.number_input("Offset Right", step=0.1, key="lib_h_osr"),
                               "sp_off_l": c1.number_input("SP Offset L", value=0.0, key="lib_h_spl"), 
                               "sp_off_r": c2.number_input("SP Offset R", value=0.0, key="lib_h_spr"),
                               "weight": st.number_input("Weight (g)", step=0.1, key="lib_h_w")}
            elif cat in ["Spoke", "Nipple"]:
                lib_payload = {cat.lower(): name, "weight": st.number_input("Unit Weight (g)", format="%.3f", step=0.001, key=f"lib_{cat.lower()}_w")}
            
            if st.form_submit_button("Save to Airtable"):
                if not name:
                    st.error("Name is required.")
                else:
                    base.table(f"{cat.lower()}s").create(lib_payload)
                    st.cache_data.clear()
                    st.success(f"{name} added!")
                    st.rerun()

    lib_choice = st.radio("View Inventory:", ["rims", "hubs", "spokes", "nipples"], horizontal=True, key="lib_view_choice")
    df_l = fetch_data(lib_choice, "id")
    if not df_l.empty:
        st.dataframe(df_l.drop(columns=['id', 'label'], errors='ignore'), use_container_width=True)
