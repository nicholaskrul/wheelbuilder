import streamlit as st
import pandas as pd
import math
from datetime import datetime
from pyairtable import Api

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Wheelbuilder Lab v10.5", layout="wide", page_icon="🚲")

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
    """Fetches data and standardizes the primary identifier column."""
    try:
        table = base.table(table_name)
        records = table.all()
        if not records: return pd.DataFrame()
        
        data = []
        for rec in records:
            fields = rec['fields']
            fields['id'] = rec['id']
            # Standardize the 'label' based on your specific primary header
            if label_col in fields:
                fields['label'] = str(fields[label_col]).strip()
            data.append(fields)
        
        df = pd.DataFrame(data)
        # Clean up any lists returned by Airtable
        for col in df.columns:
            df[col] = df[col].apply(lambda x: x[0] if isinstance(x, list) else x)
        return df
    except:
        return pd.DataFrame()

# --- 3. THE v10.5 CALCULATION ENGINE ---
def calculate_spoke(erd, fd, os, holes, crosses, is_sp=False, sp_off=0.0):
    """Precision math for J-Bend and Straightpull hubs."""
    if not erd or not fd or not holes: return 0.0
    r_rim, r_hub = float(erd) / 2, float(fd) / 2
    angle_rad = math.radians((float(crosses) * 720.0) / float(holes))
    
    if not is_sp:
        # Standard J-Bend Geometry
        l_sq = (r_rim**2) + (r_hub**2) + (float(os)**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        return round(math.sqrt(max(0, l_sq)) - 1.2, 1)
    else:
        # Straightpull Geometry with Offset
        base_l_sq = (r_rim**2) + (r_hub**2) - (2 * r_rim * r_hub * math.cos(angle_rad))
        length = math.sqrt(max(0, base_l_sq + float(os)**2)) + float(sp_off)
        return round(length, 1)

# --- 4. MAIN UI ---
st.title("🚲 Wheelbuilder Lab v10.5")
st.caption(f"Connected to Airtable Base: {AIRTABLE_BASE_ID}")

tabs = st.tabs(["🚀 Workshop Pipeline", "🧮 Spoke Calc", "📦 Component Library"])

# --- TAB 1: PIPELINE ---
with tabs[0]:
    st.subheader("🏁 Active Builds")
    df_builds = fetch_data("builds", "customer")
    if not df_builds.empty:
        for _, row in df_builds.sort_values('id', ascending=False).iterrows():
            with st.expander(f"🛠️ {row.get('customer', 'Unknown')} — {row.get('status', 'In Progress')}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Front:** {row.get('f_rim')}\n{row.get('f_l')} / {row.get('f_r')} mm")
                c2.write(f"**Rear:** {row.get('r_rim')}\n{row.get('r_l')} / {row.get('r_r')} mm")
                
                # Edit Build Logic
                new_stat = c3.selectbox("Status", ["Order Received", "Building", "Complete"], key=f"st_{row['id']}", 
                                        index=["Order Received", "Building", "Complete"].index(row['status']) if row['status'] in ["Order Received", "Building", "Complete"] else 0)
                if new_stat != row['status']:
                    base.table("builds").update(row['id'], {"status": new_stat})
                    st.rerun()
    else: st.info("No builds found.")

# --- TAB 2: CALC ---
with tabs[1]:
    st.header("🧮 Precision Lengths")
    df_rims = fetch_data("rims", "rim")
    df_hubs = fetch_data("hubs", "hub")
    
    if not df_rims.empty and not df_hubs.empty:
        col1, col2 = st.columns(2)
        r_sel = col1.selectbox("Select Rim", df_rims['label'])
        h_sel = col2.selectbox("Select Hub", df_hubs['label'])
        
        rd = df_rims[df_rims['label'] == r_sel].iloc[0]
        hd = df_hubs[df_hubs['label'] == h_sel].iloc[0]
        
        st.divider()
        is_sp = st.toggle("Straightpull Hub Logic?", value=True)
        holes = st.number_input("Spoke Count", value=int(rd.get('holes', 28)))
        
        # Calculations
        l_len = calculate_spoke(rd.get('erd',0), hd.get('fd_l',0), hd.get('os_l',0), holes, 3, is_sp, hd.get('sp_off_l',0))
        r_len = calculate_spoke(rd.get('erd',0), hd.get('fd_r',0), hd.get('os_r',0), holes, 3, is_sp, hd.get('sp_off_r',0))
        
        st.metric("Left Spoke", f"{l_len} mm")
        st.metric("Right Spoke", f"{r_len} mm")
        
        if st.button("🚀 Register Build with these Lengths"):
            st.info("Form logic can be added here to push directly to 'builds' table.")
    else: st.warning("Please check your 'rims' and 'hubs' tables in Airtable.")

# --- TAB 3: LIBRARY ---
with tabs[2]:
    choice = st.radio("View Table:", ["rims", "hubs", "builds"], horizontal=True)
    st.dataframe(fetch_data(choice, "id"), use_container_width=True)
