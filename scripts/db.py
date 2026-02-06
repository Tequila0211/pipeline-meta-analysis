import sqlite3
import os
import pandas as pd

DB_PATH = 'state.sqlite'

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Table docs based on Section 5.1
    c.execute('''
        CREATE TABLE IF NOT EXISTS docs (
            doc_id TEXT PRIMARY KEY,
            pdf_path TEXT,
            status TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            matched_reference_id TEXT,
            triage_label TEXT,
            needs_images INTEGER DEFAULT 0,
            lock_owner TEXT,
            lock_ts DATETIME
        )
    ''')
    conn.commit()
    conn.close()

def sync_from_index():
    """Syncs docs from pdf_index.csv to sqlite if they don't exist"""
    if not os.path.exists('pdf_index.csv'):
        return
    
    df = pd.read_csv('pdf_index.csv')
    conn = get_connection()
    c = conn.cursor()
    
    for _, row in df.iterrows():
        doc_id = row['doc_id']
        path = row['pdf_path']
        
        # Check if exists
        c.execute("SELECT doc_id FROM docs WHERE doc_id = ?", (doc_id,))
        if not c.fetchone():
            c.execute("INSERT INTO docs (doc_id, pdf_path, status) VALUES (?, ?, ?)", 
                      (doc_id, path, 'indexed'))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    sync_from_index()
    print("Database initialized and synced.")
