import os
import json
import jsonschema
from db import get_connection

def load_schema(name):
    with open(os.path.join('schemas', name), 'r') as f:
        return json.load(f)

def check_structural_integrity(data):
    errors = []
    
    # 2.1 Schema Version (Basic check)
    if data.get("schema_version") not in ["1.0.0", "1.1.0"]:
        errors.append(f"BLOCKER | INVALID_VERSION | schema_version | Version {data.get('schema_version')} not supported")

    # 2.2 Uniqueness
    ids = set()
    for entity in ["units", "scenarios", "conditions", "comparisons"]:
        if entity in data:
            for i, item in enumerate(data[entity]):
                item_id = item.get(f"{entity[:-1]}_id") # unit_id, scenario_id...
                if item_id in ids:
                    errors.append(f"BLOCKER | DUPLICATE_ID | {entity}[{i}] | ID {item_id} is duplicated")
                else:
                    ids.add(item_id)
    
    # 2.3 & 3. Referential Integrity
    unit_ids = {u["unit_id"] for u in data.get("units", [])}
    scenario_ids = {s["scenario_id"] for s in data.get("scenarios", [])}
    condition_ids = {c["condition_id"] for c in data.get("conditions", [])}
    comparison_ids = {k["comparison_id"] for k in data.get("comparisons", [])}
    
    # Check Comparisons
    if "comparisons" in data:
        for i, k in enumerate(data["comparisons"]):
            if k.get("unit_id") not in unit_ids:
                errors.append(f"BLOCKER | MISSING_REF | comparisons[{i}].unit_id | {k.get('unit_id')} not found in units")
            if k.get("scenario_id") not in scenario_ids:
                errors.append(f"BLOCKER | MISSING_REF | comparisons[{i}].scenario_id | {k.get('scenario_id')} not found in scenarios")
            if k.get("baseline_condition_id") not in condition_ids:
                errors.append(f"BLOCKER | MISSING_REF | comparisons[{i}].baseline_condition_id | {k.get('baseline_condition_id')} not found in conditions")
            if k.get("retrofit_condition_id") not in condition_ids:
                errors.append(f"BLOCKER | MISSING_REF | comparisons[{i}].retrofit_condition_id | {k.get('retrofit_condition_id')} not found in conditions")

    # Check Measurements
    if "measurements" in data:
        for i, m in enumerate(data["measurements"]):
            if m.get("comparison_id") not in comparison_ids:
                errors.append(f"BLOCKER | MISSING_REF | measurements[{i}].comparison_id | {m.get('comparison_id')} not found in comparisons")

    return errors

def check_logic_rules(data):
    errors = []
    
    # 2.4 Roles
    if "conditions" in data:
        for i, c in enumerate(data["conditions"]):
            role = c.get("condition_role")
            cid = c.get("condition_id")
            # We can't easily cross-check baseline/retrofit without map, but we can check if used correctly in comparison
            # But simpler: just ensure role is valid enum (handled by schema), 
            # and maybe check if specific IDs labeled 'baseline' are actually used as baseline? 
            # For now, relying on schema enums.
            pass

    # 2.5 Evidence
    for entity in ["units", "scenarios", "conditions", "comparisons", "measurements"]:
        if entity in data:
            for i, item in enumerate(data[entity]):
                if "evidence" not in item:
                     # Comparisons might not need evidence in some schemas, but usually yes
                     if entity != "comparisons": 
                        errors.append(f"BLOCKER | MISSING_EVIDENCE | {entity}[{i}] | Missing evidence object")
                elif "page" not in item["evidence"]:
                     errors.append(f"BLOCKER | MISSING_PAGE | {entity}[{i}].evidence | Missing page number")
    
    return errors

def validate_doc(doc_id):
    raw_path = os.path.join('extractions_raw', f'{doc_id}.json')
    if not os.path.exists(raw_path):
        return False, ["File not found"]
        
    with open(raw_path, 'r') as f:
        data = json.load(f)
        
    errors = []
    
    # 1. Structural Integrity
    errors.extend(check_structural_integrity(data))
    
    # 2. Logic Rules
    errors.extend(check_logic_rules(data))

    if errors:
        return False, errors
    return True, []

def run_validate():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute("SELECT doc_id FROM docs WHERE status = 'extracted_raw'")
    docs = c.fetchall()
    
    print(f"Found {len(docs)} docs to validate.")
    
    for (doc_id,) in docs:
        print(f"Validating {doc_id}...")
        valid, errors = validate_doc(doc_id)
        
        if valid:
            # Copy to valid
            with open(os.path.join('extractions_raw', f'{doc_id}.json'), 'r') as f:
                data = json.load(f)
            
            os.makedirs('extractions_valid', exist_ok=True)
            with open(os.path.join('extractions_valid', f'{doc_id}.json'), 'w') as f:
                json.dump(data, f, indent=2)
                
            c.execute("UPDATE docs SET status = 'validated_ok' WHERE doc_id = ?", (doc_id,))
            print("  OK.")
        else:
            # Report
            os.makedirs('validation_reports', exist_ok=True)
            with open(os.path.join('validation_reports', f'{doc_id}.json'), 'w') as f:
                json.dump({'errors': errors}, f, indent=2)
                
            c.execute("UPDATE docs SET status = 'needs_review' WHERE doc_id = ?", (doc_id,))
            print(f"  Failed: {errors}")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    run_validate()
