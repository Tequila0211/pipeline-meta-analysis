import json
import sqlite3
import os

def break_data():
    path = "extractions_raw/TEST_DOC_01.json"
    with open(path, 'r') as f:
        data = json.load(f)
    
    # Break integrity: Measurement pointing to non-existent comparison
    if data['measurements']:
        data['measurements'][0]['comparison_id'] = "INVALID_ID_999"
        
    with open(path, 'w') as f:
        json.dump(data, f)
        
    # Reset status so validator picks it up
    conn = sqlite3.connect('state.sqlite')
    c = conn.cursor()
    c.execute("UPDATE docs SET status = 'extracted_raw' WHERE doc_id = 'TEST_DOC_01'")
    conn.commit()
    conn.close()
    
    print("Broke data and reset status.")

if __name__ == "__main__":
    break_data()
