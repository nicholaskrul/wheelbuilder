import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v16.5", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
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

# --- 3. ANALYTICS HELPERS ---
def get_comp_data(df, label):
    if df.empty or not label: return {}
    target = str(label).strip().lower()
    df_norm = df.copy()
    df_norm['match_label'] = df_norm['label'].str.strip().str.lower()
    match = df_norm[df_norm['match_label'] == target]
    return match.iloc[0].to_dict() if not match.empty else {}

def calculate_spoke(erd, fd, lateral_os, holes, crosses, is_sp=False, sp_rad_off=0.0):
    """
    Precision Spoke Calculation Engine
    erd: Effective Rim Diameter
    fd: Flange Diameter (PCD)
    lateral_os: Hub center to flange center
    holes: Hole count
    crosses: Number of crosses
    is_sp: Straightpull toggle
    sp_rad_off: Radial distance from axle to SP socket (compensates for socket depth)
    """
    if not erd or not fd or not holes: return 0.0
    
    R = float(erd) / 2
    f = float(fd) / 2
    d = float(lateral_os)
    
    # Calculate the angle based on crosses (720 / holes per cross)
    angle_rad = math.radians((float(crosses) * 720.0) / float(holes))
    
    if not is_sp:
        # Standard J-Bend Cosine Rule
        # 1.2mm deduction accounts for J-bend elbow stretch and nipple bed engagement
        l_sq = (R**2) + (f**2) + (d**2) - (2 * R * f * math.cos(angle_rad))
        return round(math.sqrt(max(0, l_sq)) - 1.2, 1)
    else:
        # TANGENTIAL STRAIGHTPULL LOGIC
        # We use the user-defined radial offset as the start-point radius
        r_hub = float(sp_rad_off) if float(sp_rad_off) > 0 else f
        
        # Tangential math accounts for the fact that the spoke points past the axle center.
        # This increases the effective 'stretch' around the hub body.
        flat_l_sq = (R**2) + (r_hub**2) - (2 * R * r_hub * math.cos(angle_rad))
        total_l = math.sqrt(max(0, flat_l_sq + d**2))
        
        # 0.2mm deduction for Straightpull (no elbow stretch, only nipple seat engagement)
        return round(total_l - 0.2, 1)

# --- 4. SESSION STATE ---
if 'build_stage' not in st.session_state:
    st.session_state.build_stage = {
        'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0,
        'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0
    }

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v16.5")
st.caption("Workshop Command Center | Tangential SP Engine v2.0")

tabs = st.tabs(["🏁 Workshop", "🧮 Precision Calc", "📜 Proven Recipes", "➕ Register Build", "📦 Library"])

# --- TAB 1: WORKSHOP ---
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
            s_data, n_data = get_comp_data(df_spokes, row.get('spoke')), get_comp_data(df_nipples, row.get('nipple'))
            sw, nw = float(s_data.get('weight', 0)), float(n_data.get('weight', 0))
            
            f_calc = {"total": 0.0, "exists": False, "rim_w": 0.0, "hub_w": 0.0}
            if row.get('f_rim'):
                frd, fhd = get_comp_data(df_rims, row.get('f_rim')), get_comp_data(df_hubs, row.get('f_hub'))
                if frd:
                    f_calc.update({"exists": True, "rim_w": float(frd.get('weight', 0)), "hub_w": float(fhd.get('weight', 0)), "holes": int(frd.get('holes', 24))})
                    f_calc["total"] = f_calc["rim_w"] + f_calc["hub_w"] + (f_calc["holes"] * (sw + nw))

            r_calc = {"total": 0.0, "exists": False, "rim_w": 0.0, "hub_w": 0.0}
            if row.get('r_rim'):
                rrd, rhd = get_comp_data(df_rims, row.get('r_rim')), get_comp_data(df_hubs, row.get('r_hub'))
                if rrd:
                    r_calc.update({"exists": True, "rim_w": float(rrd.get('weight', 0)), "hub_w": float(rhd.get('weight', 0)), "holes": int(rrd.get('holes', 24))})
                    r_calc["total"] = r_calc["rim_w"] + r_calc["hub_w"] + (r_calc["holes"] * (sw + nw))

            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status')} ({row.get('date', '---')})"):
                cur_stat = row.get('status', 'Order Received')
                new_stat = st.selectbox("Status", ["Order Received", "Parts Received", "Building", "Complete"], key=f"st_{row['id']}", index=["Order Received", "Parts Received", "Building", "Complete"].index(cur_stat))
                if new_stat != cur_stat:
                    base.table("builds").update(row['id'], {"status": new_stat}); st.cache_data.clear(); st.rerun()
                st.divider()
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**🔘 FRONT**")
                    if f_calc["exists"]:
                        st.write(f"**Rim:** {row.get('f_rim')}\n**Hub:** {row.get('f_hub')}")
                        st.info(f"📏 L: {row.get('f_l')} / R: {row.get('f_r')} mm")
                with c2:
                    st.markdown("**🔘 REAR**")
                    if r_calc["exists"]:
                        st.write(f"**Rim:** {row.get('r_rim')}\n**Hub:** {row.get('r_hub')}")
                        st.success(f"📏 L: {row.get('r_l')} / R: {row.get('r_r')} mm")
                with c3:
                    st.metric("📦 SET WEIGHT", f"{int(f_calc['total'] + r_calc['total'])}g")
                    with st.popover("📝 Details"):
                        fs = st.text_input("Front Serial", value=row.get('f_rim_serial', ''), key=f"fs_{row['id']}")
                        rs = st.text_input("Rear Serial", value=row.get('r_rim_serial', ''), key=f"rs_{row['id']}")
                        nt = st.text_area("Build Notes", value=row.get('notes', ''), key=f"nt_{row['id']}")
                        if st.button("Save", key=f"btn_{row['id']}", use_container_width=True):
                            base.table("builds").update(row['id'], {"f_rim_serial": fs, "r_rim_serial": rs, "notes": nt})
                            st.cache_data.clear(); st.rerun()

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
        
        l_len = calculate_spoke(rd.get('erd',0), hd.get('fd_l',0), hd.get('os_l',0), holes, cross, is_sp, hd.get('sp_off_l',0))
        r_len = calculate_spoke(rd.get('erd',0), hd.get('fd_r',0), hd.get('os_r',0), holes, cross, is_sp, hd.get('sp_off_r',0))
        
        st.metric("Left Spoke", f"{l_len} mm"); st.metric("Right Spoke", f"{r_len} mm")
        
        target = st.radio("Stage results for:", ["Front Wheel", "Rear Wheel"], horizontal=True, key="calc_target")
        save_to_db = st.checkbox("💾 Save to Proven Recipe Archive", value=True, key="save_recipe")
        
        if st.button("💾 Stage & Save Data", key="calc_stage_btn", use_container_width=True):
            if target == "Front Wheel": st.session_state.build_stage.update({'f_rim': r_sel, 'f_hub': h_sel, 'f_l': l_len, 'f_r': r_len})
            else: st.session_state.build_stage.update({'r_rim': r_sel, 'r_hub': h_sel, 'r_l': l_len, 'r_r': r_len})
            
            if save_to_db:
                db_table = base.table("spoke_db")
                sp_tag = "(SP)" if is_sp else "(JB)"
                fingerprint = f"{r_sel} | {h_sel} | {holes}h | {cross}x {sp_tag}"
                escaped_fp = fingerprint.replace("'", "\\'")
                try:
                    existing = db_table.all(formula=f"{{combo_id}}='{escaped_fp}'")
                    if existing:
                        db_table.update(existing[0]['id'], {"build_count": existing[0]['fields'].get('build_count', 1) + 1, "len_l": l_len, "len_r": r_len})
                    else:
                        db_table.create({"rim": [rd['id']], "hub": [hd['id']], "holes": holes, "crosses": cross, "is_sp": is_sp, "len_l": l_len, "len_r": r_len, "build_count": 1})
                    st.toast("Recipe archived!")
                except Exception as e: st.error(f"Sync error: {e}")
            st.success(f"Staged {target}!")

# --- TAB 3: PROVEN RECIPES ---
with tabs[2]:
    st.header("📜 Proven Recipe Archive")
    df_recipes = fetch_data("spoke_db", "combo_id")
    if not df_recipes.empty:
        r_search = st.text_input("🔍 Search Recipes", key="recipe_search")
        if r_search: df_recipes = df_recipes[df_recipes['label'].str.contains(r_search, case=False, na=False)]
        st.dataframe(df_recipes[['label', 'len_l', 'len_r', 'build_count']].rename(columns={'label': 'Recipe', 'len_l': 'L-Len', 'len_r': 'R-Len', 'build_count': 'Hits'}), use_container_width=True, hide_index=True)

# --- TAB 4: REGISTER BUILD ---
with tabs[3]:
    st.header("📝 Register New Build")
    build_type = st.radio("Config:", ["Full Wheelset", "Front Only", "Rear Only"], horizontal=True, key="reg_type")
    with st.form("reg_form_v16_5"):
        cust = st.text_input("Customer Name")
        inv = st.text_input("Invoice URL")
        payload = {"customer": cust, "date": datetime.now().strftime("%Y-%m-%d"), "status": "Order Received", "invoice_url": inv}
        cf, cr = st.columns(2)
        if build_type in ["Full Wheelset", "Front Only"]:
            with cf:
                st.subheader("Front")
                fr = st.text_input("Rim", value=st.session_state.build_stage['f_rim'], key="reg_fr")
                fh = st.text_input("Hub", value=st.session_state.build_stage['f_hub'], key="reg_fh")
                fl, frr = st.number_input("L-Len", value=st.session_state.build_stage['f_l']), st.number_input("R-Len", value=st.session_state.build_stage['f_r'])
                payload.update({"f_rim": fr, "f_hub": fh, "f_l": fl, "f_r": frr})
        if build_type in ["Full Wheelset", "Rear Only"]:
            with cr:
                st.subheader("Rear")
                rr = st.text_input("Rim", value=st.session_state.build_stage['r_rim'], key="reg_rr")
                rh = st.text_input("Hub", value=st.session_state.build_stage['r_hub'], key="reg_rh")
                rl, rrr = st.number_input("L-Len ", value=st.session_state.build_stage['r_l']), st.number_input("R-Len ", value=st.session_state.build_stage['r_r'])
                payload.update({"r_rim": rr, "r_hub": rh, "r_l": rl, "r_r": rrr})
        sc1, sc2 = st.columns(2)
        payload.update({"spoke": sc1.selectbox("Spoke", df_spokes['label'] if not df_spokes.empty else ["Std"], key="reg_spk"),
                        "nipple": sc2.selectbox("Nipple", df_nipples['label'] if not df_nipples.empty else ["Std"], key="reg_nip"),
                        "notes": st.text_area("Build Journal", key="reg_nt")})
        if st.form_submit_button("🚀 Finalize Build"):
            if cust:
                base.table("builds").create(payload)
                st.session_state.build_stage = {'f_rim': '', 'f_hub': '', 'f_l': 0.0, 'f_r': 0.0, 'r_rim': '', 'r_hub': '', 'r_l': 0.0, 'r_r': 0.0}
                st.cache_data.clear(); st.success("Registered!"); st.rerun()
            else: st.error("Customer name is required.")

# --- TAB 5: LIBRARY ---
with tabs[4]:
    st.header("📦 Library Management")
    with st.expander("➕ Add New Component"):
        cat = st.radio("Category", ["Rim", "Hub", "Spoke", "Nipple"], horizontal=True, key="lib_cat")
        with st.form("lib_add_v16_5"):
            name = st.text_input("Component Name")
            c1, c2 = st.columns(2)
            lib_p = {}
            if cat == "Rim": lib_p = {"rim": name, "erd": c1.number_input("ERD (mm)", step=0.1), "holes": c2.number_input("Hole Count", step=1, value=24), "weight": st.number_input("Weight (g)", step=0.1)}
            elif cat == "Hub": lib_p = {"hub": name, "fd_l": c1.number_input("FD Left", step=0.1), "fd_r": c2.number_input("FD Right", step=0.1), "os_l": c1.number_input("Offset L", step=0.1), "os_r": c2.number_input("Offset R", step=0.1), "sp_off_l": c1.number_input("SP Offset L", value=0.0), "sp_off_r": c2.number_input("SP Offset R", value=0.0), "weight": st.number_input("Weight (g)", step=0.1)}
            elif cat in ["Spoke", "Nipple"]: lib_p = {cat.lower(): name, "weight": st.number_input("Unit Weight (g)", format="%.3f", step=0.001)}
            if st.form_submit_button("Save to Library"):
                if name: base.table(f"{cat.lower()}s").create(lib_p); st.cache_data.clear(); st.success("Added!"); st.rerun()
    
    v_cat = st.radio("Inventory View:", ["rims", "hubs", "spokes", "nipples"], horizontal=True, key="lib_v")
    df_l = fetch_data(v_cat, "id")
    if not df_l.empty:
        l_search = st.text_input("🔍 Search Library", key="lib_search")
        if l_search:
            # We search across all columns for the library
            df_l = df_l[df_l.apply(lambda row: row.astype(str).str.contains(l_search, case=False).any(), axis=1)]
        st.dataframe(df_l.drop(columns=['id', 'label'], errors='ignore'), use_container_width=True, hide_index=True)
