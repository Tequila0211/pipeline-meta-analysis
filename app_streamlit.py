import streamlit as st
import sqlite3
import pandas as pd
import json
import os
import glob
from scripts.db import get_connection

st.set_page_config(layout="wide")
st.title("Meta-Analysis Extraction Review")

# Connect to DB
conn = get_connection()
c = conn.cursor()

# Sidebar: Filter by status
status_filter = st.sidebar.selectbox("Status", ["needs_review", "validated_ok", "approved", "extracted_raw"])

# --- Notification Logic ---
# Initialize known docs in session state if not present
if 'known_docs' not in st.session_state:
    st.session_state['known_docs'] = set()

# Refresh button to manually trigger a check
if st.sidebar.button("🔄 Check for Updates"):
    st.rerun()

# List docs
c.execute("SELECT doc_id, status FROM docs WHERE status = ?", (status_filter,))
docs = c.fetchall()

# Check for new documents (only if looking at extracted_raw or other relevant statuses)
current_doc_ids = {doc[0] for doc in docs}
new_docs = current_doc_ids - st.session_state['known_docs']

if new_docs:
    # If this is the very first run (known_docs empty), just load them without notification
    # logic to avoid spamming on startup, OR just notify. 
    # Let's notify only if we already knew some docs, or just simple toast for "Ready"
    if st.session_state['known_docs']:
        count = len(new_docs)
        if count == 1:
            st.toast(f"📄 New document ready: {list(new_docs)[0]}", icon="✅")
        else:
            st.toast(f"✅ {count} new documents ready for review!", icon="🎉")
    
    # Update known state
    st.session_state['known_docs'].update(current_doc_ids)
# --------------------------

if not docs:
    st.sidebar.warning("No docs found for this status.")
    doc_id = None
else:
    doc_options = [doc[0] for doc in docs]
    doc_id = st.sidebar.selectbox("Select Document", doc_options)

if doc_id:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("PDF / Text")
        # Load pages text
        files = sorted(glob.glob(os.path.join('pages_text', doc_id, 'page_*.txt')))
        text_content = ""
        for f in files:
            with open(f, 'r', encoding='utf-8') as tf:
                text_content += f"--- {os.path.basename(f)} ---\n" + tf.read() + "\n"
        
        st.text_area("Full Text Content", text_content, height=800)
        # Ideally embed PDF here, but for MVP local text is easier

    with col2:
        st.header("Extraction Data")
        
        # Load validation or raw
        # Try approved -> valid -> raw
        paths = [
            os.path.join('extractions_approved', f'{doc_id}.json'),
            os.path.join('extractions_valid', f'{doc_id}.json'),
            os.path.join('extractions_raw', f'{doc_id}.json')
        ]
        
        current_path = None
        data = {}
        for p in paths:
            if os.path.exists(p):
                current_path = p
                with open(p, 'r') as f:
                    data = json.load(f)
                break
        
        if current_path:
            st.info(f"Loaded from: {current_path}")
            
            # Form
            with st.form("review_form"):
                edited_data = st.text_area("JSON Data", json.dumps(data, indent=2), height=600)
                
                submitted = st.form_submit_button("Approve")
                rejected = st.form_submit_button("Reject")
                
                if submitted:
                    try:
                        new_data = json.loads(edited_data)
                        os.makedirs('extractions_approved', exist_ok=True)
                        with open(os.path.join('extractions_approved', f'{doc_id}.json'), 'w') as f:
                            json.dump(new_data, f, indent=2)
                        
                        c.execute("UPDATE docs SET status = 'approved' WHERE doc_id = ?", (doc_id,))
                        conn.commit()
                        st.success("Approved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving: {e}")
                        
                if rejected:
                    c.execute("UPDATE docs SET status = 'rejected' WHERE doc_id = ?", (doc_id,))
                    conn.commit()
                    st.warning("Rejected.")
                    st.rerun()
        else:
            st.warning("No extraction file found.")

conn.close()
