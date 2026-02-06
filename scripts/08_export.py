import os
import json
import pandas as pd
import glob
from db import get_connection

def run_export():
    conn = get_connection()
    c = conn.cursor()
    
    # Priority: Approved > Valid
    # We select all docs that have valid data
    c.execute("SELECT doc_id FROM docs WHERE status IN ('approved', 'validated_ok')")
    docs = c.fetchall()
    
    unified_rows = []
    
    for (doc_id,) in docs:
        path = os.path.join('extractions_approved', f'{doc_id}.json')
        if not os.path.exists(path):
            path = os.path.join('extractions_valid', f'{doc_id}.json')
            
        if not os.path.exists(path):
            continue
            
        with open(path, 'r') as f:
            data = json.load(f)
            
        # Flatten structure for unified_outcomes
        if 'measurements' in data and data['measurements']:
            for m in data['measurements']:
                row = {
                    'project_id': data.get('project_id'),
                    'reference_id': data.get('reference_id'),
                    'doc_id': doc_id,
                    'study_type': data.get('study', {}).get('study_type'),
                    'building_type': data.get('building', {}).get('building_type'),
                    'comparison_id': m.get('comparison_id'),
                    'outcome_family': m.get('outcome_family'),
                    'baseline_value': m.get('baseline_value'),
                    'retrofit_value': m.get('retrofit_value'),
                    'unit': m.get('unit'),
                }
                
                # Calculate diff
                if row['baseline_value'] is not None and row['retrofit_value'] is not None:
                    row['raw_diff'] = row['retrofit_value'] - row['baseline_value']
                else:
                    row['raw_diff'] = None
                    
                unified_rows.append(row)

    os.makedirs('exports', exist_ok=True)
    
    if unified_rows:
        df = pd.DataFrame(unified_rows)
        df.to_csv('exports/unified_outcomes.csv', index=False)
        print(f"Exported {len(df)} rows to exports/unified_outcomes.csv")
    else:
        print("No data to export.")

if __name__ == "__main__":
    run_export()
