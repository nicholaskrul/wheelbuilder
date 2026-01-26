import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import math
from datetime import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="ProWheel Lab v7.9", layout="wide", page_icon="🚲")

# --- 2. GOOGLE SHEETS CONNECTION ---
# cite: 6
conn = st.connection("gsheets", type=GSheetsConnection)

def get_worksheet_data(sheet_name, force_refresh=False):
    # Set ttl to 600 seconds (10 mins) to prevent 429 Quota errors.
    # Manual refreshes or form submissions will override this.
    return conn.read(worksheet=sheet_name, ttl=0 if force_refresh else 600)

# --- 3. RE-CALIBRATED CALCULATION LOGIC ---
# cite: 5, 6
def calculate_precision_spoke(erd, fd, os, holes, crosses, is_sp, sp_offset, hole_diam=2.4, round_mode="None"):
    if 0 in [erd, fd, holes]: return 0.0
    r_rim, r_hub = erd / 2, fd / 2
    
    if not is_sp:
        # Standard J-Bend Geometry (Matches v6.4 accuracy)
        alpha_rad = math.radians((crosses * 720.0) / holes)
        l_sq = (r_rim**2) + (r_hub**2) + (os**2) - (2 * r_rim * r_hub * math.cos(alpha_rad))
        # Deduction of half-hole diameter (approx 1.2mm)
        length = math.sqrt(max(0, l_sq)) - (hole_diam / 2)
    else:
        # Straightpull Logic (Matches 304.2 / 305.5 benchmarks)
        d_tangent_2d = math.sqrt(max(0, r_rim**2 - r_hub**2))
        length = math.sqrt(d_tangent_2d**2 + os**2) + sp_offset
        
    # --- ROUNDING LOGIC ---
    if round_mode == "Nearest Even":
        return float(round(length / 2) * 2)
    elif round_mode == "Nearest Odd":
        return float(round((length - 1) / 2) * 2 + 1)
    return round(length, 1)

# Initialize Session State for staging lengths across tabs
for key in ['f_l', 'f_r', 'r_l', 'r_r']:
    if key not in st.session_state: st.session_state[key] = 0.0

# --- 4. MAIN USER INTERFACE ---
st.title("🚲 ProWheel Lab v7.9: Streamlined Business Suite")
st.markdown("---")

tabs = st.tabs(["📊 Dashboard", "🧮 Precision Calc", "📦 Library", "➕ Register Build", "📄 Spec Sheet"])

# --- TAB: DASHBOARD ---
with tabs[0]:
    st.subheader("🏁 Workshop Pipeline")
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    try:
        df_b = get_worksheet_data("builds") # cite: 2
        if not df_b.empty:
            st.dataframe(df_b, use_container_width=True, hide_index=True)
        else:
            st.info("No builds found. Populate your Library and Register a Build.")
    except Exception as e:
        st.error(f"Connect to 'builds' tab failed: {e}")

# --- TAB: PRECISION CALC ---
with tabs[1]:
    st.header("🧮 Integrated Calculator")
    try:
        df_rims, df_hubs = get_worksheet_data("rims"), get_worksheet_data("hubs")
        calc_mode = st.radio("Source", ["Use Library", "Manual Entry"], horizontal=True)
        
        if calc_mode == "Use Library" and not df_rims.empty and not df_hubs.empty:
            c1, c2 = st.columns(2)
            rim_choice = c1.selectbox("Select Rim", df_rims['brand'] + " " + df_rims['model'])
            hub_choice = c2.selectbox("Select Hub (Current Calc)", df_hubs['brand'] + " " + df_hubs['model'])
            sel_r = df_rims[(df_rims['brand'] + " " + df_rims['model']) == rim_choice].iloc[0]
            sel_h = df_hubs[(df_hubs['brand'] + " " + df_hubs['model']) == hub_choice].iloc[0]
            erd, holes = sel_r['erd'], sel_r['holes']
            l_fd, r_fd, l_os, r_os, l_sp, r_sp = sel_h['fd_l'], sel_h['fd_r'], sel_h['os_l'], sel_h['os_r'], sel_h['sp_off_l'], sel_h['sp_off_r']
        else:
            m1, m2 = st.columns(2)
            erd, holes = m1.number_input("Rim ERD", 601.0), m2.number_input("Holes", 28)
            l_fd, r_fd, l_os, r_os, l_sp, r_sp = 40.8, 36.0, 28.0, 40.2, 1.7, 1.8

        st.divider()
        r1, r2 = st.columns(2)
        is_sp, r_mode = r1.toggle("Straightpull?", value=True), r2.selectbox("Rounding", ["None", "Nearest Even", "Nearest Odd"])
        h_diam = st.slider("Hole Diameter (mm)", 2.0, 3.0, 2.4)
        l_c, r_c = st.selectbox("L-Cross Pattern", [0,1,2,3], index=3), st.selectbox("R-Cross Pattern", [0,1,2,3], index=3)
        
        res_l = calculate_precision_spoke(erd, l_fd, l_os, holes, l_c, is_sp, l_sp, h_diam, r_mode)
        res_r = calculate_precision_spoke(erd, r_fd, r_os, holes, r_c, is_sp, r_sp, h_diam, r_mode)
        
        st.metric("Left Spoke", f"{res_l} mm")
        st.metric("Right Spoke", f"{res_r} mm")
        
        side = st.radio("Stage to:", ["Front Wheel", "Rear Wheel"], horizontal=True)
        if st.button("Apply and Stage"):
            if side == "Front Wheel": 
                st.session_state.f_l, st.session_state.f_r = res_l, res_r
            else: 
                st.session_state.r_l, st.session_state.r_r = res_l, res_r
            st.success(f"{side} staged!")
    except Exception as e: 
        st.error(f"Calc error: {e}")

# --- TAB: COMPONENT LIBRARY ---
with tabs[2]:
    st.header("📦 Library Management")
    l_type = st.selectbox("Category", ["Rims", "Hubs", "Spokes", "Nipples"])
    with st.form("lib_form", clear_on_submit=True): # cite: 6
        b, m = st.text_input("Brand"), st.text_input("Model")
        if l_type == "Rims":
            e, h = st.number_input("ERD"), st.number_input("Holes")
            if st.form_submit_button("Save Rim"):
                new = pd.DataFrame([{"brand":b, "model":m, "erd":e, "holes":h}])
                conn.update(worksheet="rims", data=pd.concat([get_worksheet_data("rims",True), new], ignore_index=True))
                st.success("Rim saved!")
        elif l_type == "Hubs":
            fl, fr, ol, orr, sl, sr = st.number_input("L-PCD"), st.number_input("R-PCD"), st.number_input("L-Dist"), st.number_input("R-Dist"), st.number_input("L-SP Off"), st.number_input("R-SP Off")
            if st.form_submit_button("Save Hub"):
                new = pd.DataFrame([{"brand":b, "model":m, "fd_l":fl, "fd_r":fr, "os_l":ol, "os_r":orr, "sp_off_l":sl, "sp_off_r":sr}])
                conn.update(worksheet="hubs", data=pd.concat([get_worksheet_data("hubs",True), new], ignore_index=True))
                st.success("Hub saved!")
        else:
             if st.form_submit_button(f"Save {l_type[:-1]}"):
                new = pd.DataFrame([{"brand":b, "model":m}])
                conn.update(worksheet=l_type.lower(), data=pd.concat([get_worksheet_data(l_type.lower(),True), new], ignore_index=True))
                st.success(f"{l_type[:-1]} saved!")

# --- TAB: REGISTER BUILD ---
with tabs[3]:
    st.header("📝 Register Build")
    try:
        df_builds, df_rims, df_hubs = get_worksheet_data("builds"), get_worksheet_data("rims"), get_worksheet_data("hubs")
        df_spokes, df_nipples = get_worksheet_data("spokes"), get_worksheet_data("nipples")
        mode = st.radio("Action", ["New Build", "Update Existing"], horizontal=True)
        
        with st.form("build_form_final", clear_on_submit=True): # cite: 6
            # Fields as requested
            cust = st.text_input("Customer Name") if mode == "New Build" else st.selectbox("Select Project", df_builds['customer'])
            
            c1, c2 = st.columns(2)
            f_h = c1.selectbox("Front Hub", df_hubs['brand'] + " " + df_hubs['model'])
            r_h = c2.selectbox("Rear Hub", df_hubs['brand'] + " " + df_hubs['model'])
            
            rim = st.selectbox("Rim", df_rims['brand'] + " " + df_rims['model'])
            
            c3, c4 = st.columns(2)
            sp = c3.selectbox("Spokes", df_spokes['brand'] + " " + df_spokes['model'])
            ni = c4.selectbox("Nipples", df_nipples['brand'] + " " + df_nipples['model'])
            
            st.write("**Spoke Lengths (mm)**")
            sc1, sc2, sc3, sc4 = st.columns(4)
            vfl = sc1.number_input("F-L", value=st.session_state.f_l)
            vfr = sc2.number_input("F-R", value=st.session_state.f_r)
            vrl = sc3.number_input("R-L", value=st.session_state.r_l)
            vrr = sc4.number_input("R-R", value=st.session_state.r_r)
            
            inv = st.text_input("Invoice URL (Zoho Books)")
            notes = st.text_area("Notes")
            
            if st.form_submit_button("Sync Build"):
                entry = {
                    "date": datetime.now().strftime("%Y-%m-%d"), 
                    "customer": cust, 
                    "f_hub": f_h, 
                    "r_hub": r_h, 
                    "rim": rim, 
                    "spoke": sp, 
                    "nipple": ni, 
                    "f_l": vfl, 
                    "f_r": vfr, 
                    "r_l": vrl, 
                    "r_r": vrr, 
                    "invoice_url": inv, 
                    "notes": notes
                }
                if mode == "Update Existing": 
                    df_builds = df_builds[df_builds['customer'] != cust]
                
                df_up = pd.concat([df_builds, pd.DataFrame([entry])], ignore_index=True)
                conn.update(worksheet="builds", data=df_up)
                st.success("Build Successfully Synced!")
                st.rerun()
    except Exception as e: 
        st.warning(f"Error: {e}. Ensure Library is populated.")

# --- TAB: SPEC SHEET ---
with tabs[4]:
    st.header("📄 Build Portfolio")
    df_builds = get_worksheet_data("builds")
    if not df_builds.empty:
        target = st.selectbox("Select Build to View", df_builds['customer'])
        d = df_builds[df_builds['customer'] == target].iloc[0]
        
        st.markdown(f"### Build for: **{target}**")
        st.caption(f"Created: {d['date']}")
        st.divider()
        
        col_parts, col_lens = st.columns([1, 1])
        with col_parts:
            st.markdown("#### 📦 Components")
            st.write(f"**Rim:** {d['rim']}")
            st.write(f"**Front Hub:** {d['f_hub']}")
            st.write(f"**Rear Hub:** {d['r_hub']}")
            st.write(f"**Spokes:** {d['spoke']}")
            st.write(f"**Nipples:** {d['nipple']}")
        
        with col_lens:
            st.markdown("#### 📏 Spoke Lengths")
            st.info(f"**Front Wheel:** L {d['f_l']} / R {d['f_r']} mm")
            st.success(f"**Rear Wheel:** L {d['r_l']} / R {d['r_r']} mm")
            
        st.divider()
        if d['invoice_url']: 
            st.markdown(f"🔗 **Invoice:** [View in Zoho Books]({d['invoice_url']})")
        
        st.markdown("**Builder Notes:**")
        st.write(d['notes'] if d['notes'] else "No notes provided.")
        
        if st.button("Generate Downloadable Sheet"):
            out = f"PROWHEEL LAB BUILD PORTFOLIO\nCustomer: {target}\nDate: {d['date']}\n\n"
            out += f"COMPONENTS:\n- Rim: {d['rim']}\n- F-Hub: {d['f_hub']}\n- R-Hub: {d['r_hub']}\n- Spokes: {d['spoke']}\n- Nipples: {d['nipple']}\n\n"
            out += f"LENGTHS:\n- Front: L {d['f_l']}mm / R {d['f_r']}mm\n- Rear: L {d['r_l']}mm / R {d['r_r']}mm\n\n"
            out += f"Invoice: {d['invoice_url'] if d['invoice_url'] else 'N/A'}\nNotes: {d['notes']}"
            st.download_button("Download Text File", out, f"{target}_Specs.txt")
    else:
        st.info("No builds available.")
