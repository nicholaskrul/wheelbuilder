import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v10.6", layout="wide", page_icon="🚲")

# --- 2. AIRTABLE CONNECTION ---
try:
    AIRTABLE_API_KEY = st.secrets["airtable"]["api_key"]
    AIRTABLE_BASE_ID = st.secrets["airtable"]["base_id"]
    api = Api(AIRTABLE_API_KEY)
    base = api.base(AIRTABLE_BASE_ID)
except Exception as e:
    st.error("❌ Airtable Secrets Error: Ensure [airtable] api_key and base_id are in Streamlit Secrets.")
    st.stop()

@st.cache_data(ttl=300)
def fetch_data(table_name, label_col):
    """Fetches data and standardizes the primary identifier column based on user headers."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        
        data = []
        for rec in records:
            fields = rec['fields']
            fields['id'] = rec['id']
            # Map the specific primary column (rim or hub) to a standard 'label' for the UI
            if label_col in fields:
                fields['label'] = str(fields[label_col]).strip()
            data.append(fields)
        
        df = pd.DataFrame(data)
        # Clean up any lists returned by Airtable (Linked Records often return as lists)
        for col in df.columns:
            df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
        return df
    except:
        return pd.DataFrame()

# --- 3. THE v10.6 CALCULATION ENGINE ---
def calculate_spoke(erd, fd, os, holes, crosses, is_sp=False, sp_off=0.0):
    """Precision math for J-Bend and Straightpull hubs based on v10.4 logic."""
    if not erd or not fd or not holes: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    # Standard spoke angle based on crosses and hole count
    angle_rad = math.radians((float(crosses) * 720.0) / float(holes))
    
    if not is_sp:
        # Standard J-Bend Geometry (Law of Cosines)
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        # 1.2mm deduction for spoke seating/stretch
        return round(math.sqrt(max(0, l_sq)) - 1.2, 1)
    else:
        # Straightpull Geometry using radial base + lateral offset + hub-specific SP offset
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_off)
        return round(length, 1)

# --- 4. SESSION STATE FOR STAGING ---
if 'staged_build' not in st.session_state:
    st.session_state.staged_build = {'f_l': 0.0, 'f_r': 0.0, 'r_l': 0.0, 'r_r': 0.0}

# --- 5. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v10.6")
st.caption(f"Airtable Active | Base: {AIRTABLE_BASE_ID}")

tabs = st.tabs(["🚀 Workshop Pipeline", "🧮 Precision Calculator", "📦 Component Library"])

# --- TAB 1: WORKSHOP PIPELINE ---
with tabs[0]:
    st.subheader("🏁 Active Builds & Status")
    df_builds = fetch_data("builds", "customer")
    
    if not df_builds.empty:
        # Filter builds
        search = st.text_input("🔍 Search Customer")
        filtered_df = df_builds.copy()
        if search:
            filtered_df = filtered_df[filtered_df['label'].str.contains(search, case=False)]

        for _, row in filtered_df.sort_values('id', ascending=False).iterrows():
            with st.expander(f"🛠️ {row.get('customer')} — {row.get('status', 'In Progress')}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write(f"**Front:** {row.get('f_rim')}")
                    st.info(f"Lengths: {row.get('f_l')} / {row.get('f_r')} mm")
                with c2:
                    st.write(f"**Rear:** {row.get('r_rim')}")
                    st.success(f"Lengths: {row.get('r_l')} / {row.get('r_r')} mm")
                with c3:
                    # Quick Status Update
                    current_status = row.get('status', 'Order Received')
                    status_options = ["Order Received", "Parts Received", "Building", "Complete"]
                    new_stat = st.selectbox("Update Status", status_options, 
                                            index=status_options.index(current_status) if current_status in status_options else 0,
                                            key=f"stat_up_{row['id']}")
                    
                    if new_stat != current_status:
                        base.table("builds").update(row['id'], {"status": new_stat})
                        st.cache_data.clear()
                        st.rerun()
                
                if row.get('notes'):
                    st.caption(f"**Notes:** {row['notes']}")
    else:
        st.info("No active builds. Use the Calculator to start a new project.")

# --- TAB 2: PRECISION CALCULATOR ---
with tabs[1]:
    st.header("🧮 Spoke Length Engine")
    df_rims = fetch_data("rims", "rim")
    df_hubs = fetch_data("hubs", "hub")
    
    if not df_rims.empty and not df_hubs.empty:
        c1, c2 = st.columns(2)
        r_sel = c1.selectbox("Select Rim", df_rims['label'])
        h_sel = c2.selectbox("Select Hub", df_hubs['label'])
        
        rd = df_rims[df_rims['label'] == r_sel].iloc[0]
        hd = df_hubs[df_hubs['label'] == h_sel].iloc[0]
        
        st.divider()
        
        col_in1, col_in2, col_in3 = st.columns(3)
        is_sp = col_in1.toggle("Straightpull Hub?", value=True)
        holes = col_in2.number_input("Hole Count", value=int(rd.get('holes', 28)), step=2)
        crosses = col_in3.selectbox("Cross Pattern", [0, 1, 2, 3, 4], index=3)
        
        # Calculate results for the current selection
        l_len = calculate_spoke(rd.get('erd', 0), hd.get('fd_l', 0), hd.get('os_l', 0), holes, crosses, is_sp, hd.get('sp_off_l', 0))
        r_len = calculate_spoke(rd.get('erd', 0), hd.get('fd_r', 0), hd.get('os_r', 0), holes, crosses, is_sp, hd.get('sp_off_r', 0))
        
        m1, m2 = st.columns(2)
        m1.metric("Left Spoke", f"{l_len} mm")
        m2.metric("Right Spoke", f"{r_len} mm")
        
        st.divider()
        
        # Build Registration Form
        st.subheader("📝 Register Build to Pipeline")
        with st.form("register_build_form"):
            customer = st.text_input("Customer Name / Project ID")
            side = st.radio("Apply these lengths as:", ["Front Wheel", "Rear Wheel"], horizontal=True)
            notes = st.text_area("Build Notes (Optional)")
            
            if st.form_submit_button("Stage and Save Build"):
                if side == "Front Wheel":
                    st.session_state.staged_build['f_l'], st.session_state.staged_build['f_r'] = l_len, r_len
                    # For a simple one-off registration, we create the record now
                    base.table("builds").create({
                        "customer": customer,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "status": "Order Received",
                        "f_rim": r_sel,
                        "f_hub": h_sel,
                        "f_l": l_len,
                        "f_r": r_len,
                        "notes": notes
                    })
                else:
                    base.table("builds").create({
                        "customer": customer,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "status": "Order Received",
                        "r_rim": r_sel,
                        "r_hub": h_sel,
                        "r_l": l_len,
                        "r_r": r_len,
                        "notes": notes
                    })
                st.cache_data.clear()
                st.success(f"Build for {customer} saved to Pipeline!")
    else:
        st.warning("Ensure your Airtable 'rims' and 'hubs' tables are populated.")

# --- TAB 3: COMPONENT LIBRARY ---
with tabs[2]:
    st.header("📦 Component Library")
    lib_choice = st.radio("View Table:", ["rims", "hubs", "builds"], horizontal=True)
    df_lib = fetch_data(lib_choice, "id")
    if not df_lib.empty:
        # Remove the internal 'id' and 'label' columns for a cleaner view
        clean_view = df_lib.drop(columns=['id', 'label'], errors='ignore')
        st.dataframe(clean_view, use_container_width=True)
    else:
        st.info(f"Table '{lib_choice}' is currently empty.")
