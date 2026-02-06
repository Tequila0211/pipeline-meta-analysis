import os
import re
import yaml
import sqlite3
import glob
from db import get_connection, init_db, sync_from_index

# Regex patterns
INTERVENTION_REGEX = r"retrofit|renovat|refurbish|adaptation|passive cooling|shading|cool roof|PCM|green roof|insulation|natural ventilation"
OUTCOME_REGEX = r"overheating|discomfort hours|degree-hours|operative temperature|indoor temperature|TM52|ASHRAE|EN 16798"

def load_doc_text(doc_id):
    files = glob.glob(os.path.join('pages_text', doc_id, 'page_*.txt'))
    full_text = ""
    for f in files:
        with open(f, 'r', encoding='utf-8') as tf:
            full_text += tf.read() + "\n"
    return full_text

def apply_heuristic(text):
    has_intervention = re.search(INTERVENTION_REGEX, text, re.IGNORECASE)
    has_outcome = re.search(OUTCOME_REGEX, text, re.IGNORECASE)
    
    if has_intervention and has_outcome:
        return 'extractable'
    elif has_intervention:
        return 'maybe'
    else:
        return 'no-data'

def run_triage():
    # Ensure DB is ready
    if not os.path.exists('state.sqlite'):
        init_db()
        sync_from_index()
    
    conn = get_connection()
    c = conn.cursor()
    
    # Select docs that need triage
    # pending, indexed, or paged (assuming paged is done if text exists)
    # We'll just look for 'indexed' or 'paged' or NULL status if specific flow
    # But for now, let's process 'indexed' docs
    
    c.execute("SELECT doc_id, status FROM docs WHERE status IN ('indexed', 'paged')")
    docs = c.fetchall()
    
    print(f"Found {len(docs)} docs to triage.")
    
    for doc_id, status in docs:
        text = load_doc_text(doc_id)
        if not text:
            print(f"No text for {doc_id}, skipping.")
            continue
            
        label = apply_heuristic(text)
        print(f"Doc {doc_id[:8]}... -> {label}")
        
        # Mapping label to status
        new_status = f"triaged_{label.replace('-', '_')}"
        
        # If 'maybe', we might want AI. But for MVP step 1, we just label.
        # If AI is enabled and key is present, we would refine 'maybe'.
        
        c.execute("UPDATE docs SET triage_label = ?, status = ? WHERE doc_id = ?",
                  (label, new_status, doc_id))
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    run_triage()
