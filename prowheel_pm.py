                if cat == "Rim": p = {"rim": name, "erd": c1.number_input("ERD"), "holes": c2.number_input("Holes", value=28), "weight": st.number_input("Weight")}
                elif cat == "Hub": p = {"hub": name, "fd_l": c1.number_input("FD-L"), "fd_r": c2.number_input("FD-R"), "os_l": c1.number_input("OS-L"), "os_r": c2.number_input("OS-R"), "weight": st.number_input("Weight")}
                else: p = {cat.lower(): name, "weight": st.number_input("Weight (g)", format="%.3f")}
                
                if st.form_submit_button("Save to Database"):
                    if name: 
                        table_key = f"{cat.lower()}s"
                        new_rec = base.table(table_key).create(p)
                        p["id"] = new_rec["id"]
                        p["label"] = name
                        add_local_record(table_key, p)
                        st.success("Added to library!")
                        st.rerun()
        v_cat = st.radio("View Inventory:", ["rims", "hubs", "spokes", "nipples"], horizontal=True)
        df_lib = st.session_state.data.get(v_cat, pd.DataFrame())
        if not df_lib.empty: 
            st.dataframe(df_lib.drop(columns=['id', 'label'], errors='ignore').sort_values(df_lib.columns[0]), use_container_width=True, hide_index=True)
# =========================================================================
# --- 5. MODERN SYSTEM ROUTING DISPATCHER ---
# =========================================================================
st.markdown("<style>[data-testid='stSidebar'] { display: none !important; }</style>", unsafe_allow_html=True)
if "build" in st.query_params:
    active_page = st.Page(render_client_portal, title="Client Portal", icon="🚲")
else:
    active_page = st.Page(render_admin_pipeline, title="Admin Dashboard", icon="⚙️")
st.navigation([active_page], position="hidden").run()
