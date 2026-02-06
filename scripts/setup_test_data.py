import sqlite3
import os

def setup_test():
    if not os.path.exists('state.sqlite'):
        print("Creating DB...")
        from db import init_db
        init_db()

    conn = sqlite3.connect('state.sqlite')
    c = conn.cursor()
    
    # Ensure tables exist (if init_db didn't run or partial)
    # But db.py should handle it.
    
    # Insert or replace a test doc
    doc_id = "TEST_DOC_01"
    
    # Check if exists
    c.execute("INSERT OR REPLACE INTO docs (doc_id, status, triage_label) VALUES (?, ?, ?)", 
              (doc_id, 'triaged_extractable', 'extractable'))
    
    print(f"Inserted/Updated {doc_id} with status 'triaged_extractable'")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_test()
