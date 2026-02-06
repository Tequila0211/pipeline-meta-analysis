import os
import json
import yaml
import sqlite3
import argparse
import time
from retriever import retrieve_pages
from db import get_connection

# Placeholder for Gemini import
try:
    import google.generativeai as genai
except ImportError:
    genai = None

def load_config():
    with open('run_config.yaml', 'r') as f:
        return yaml.safe_load(f)

def load_schema(name):
    with open(os.path.join('schemas', name), 'r') as f:
        return json.load(f)

def get_mock_extraction(doc_id):
    """Returns a valid mock extraction for testing"""
    return {
        "schema_version": "1.0.0",
        "project_id": "MOCK_PROJ",
        "reference_id": "MOCK_REF",
        "doc_id": doc_id,
        "study": {
            "study_type": "simulation",
            "study_design": "Case study of retrofit",
            "notes": "Mock extraction"
        },
        "building": {
            "building_type": "residential",
            "location_country": "UK",
            "hvac_status": "mixed_mode"
        },
        "units": [
            {
                "unit_id": "U1",
                "unit_type": "building",
                "unit_label": "Semi-detached house",
                "evidence": {"page": 1, "quote": "a semi-detached house in London"}
            }
        ],
        "scenarios": [
            {
                "scenario_id": "S1",
                "scenario_label": "Typical Summer",
                "heat_context": "typical_summer",
                "time_window": {
                    "time_window_type": "seasonal_summer",
                    "definition": "June to August",
                    "occupied_hours_rule": "24h"
                },
                "evidence": {"page": 2, "quote": "Summer period (Jun-Aug)"}
            }
        ],
        "conditions": [
            {
                "condition_id": "C0",
                "condition_role": "baseline",
                "package_label": "Existing",
                "strategy_family": ["other"],
                "evidence": {"page": 1, "quote": "Baseline condition"}
            },
            {
                "condition_id": "C1",
                "condition_role": "retrofit",
                "package_label": "Cool Roof",
                "strategy_family": ["cool_roof"],
                "evidence": {"page": 2, "quote": "Cool roof installation"}
            }
        ],
        "comparisons": [
            {
                "comparison_id": "K1",
                "unit_id": "U1",
                "scenario_id": "S1",
                "baseline_condition_id": "C0",
                "retrofit_condition_id": "C1",
                "comparator_type": "before_after_same_building_controlled",
                "boundary_match_level": "high"
            }
        ],
        "measurements": [
            {
                "comparison_id": "K1",
                "outcome_family": "A",
                "metric_A": "overheating_hours",
                "comfort_standard": "TM52",
                "threshold_definition": "Criterion 1",
                "aggregation_period": "occupied",
                "baseline_value": 500,
                "retrofit_value": 100,
                "unit": "h",
                "numeric_source_quality": "text",
                "is_primary": True,
                "primary_rule_applied": "standard_priority",
                "evidence": {"page": 3, "quote": "Hours reduced from 500 to 100"}
            }
        ]
    }

def run_extract(mock=False):
    config = load_config()
    conn = get_connection()
    c = conn.cursor()
    
    # Select docs ready for extraction
    c.execute("SELECT doc_id FROM docs WHERE status = 'triaged_extractable'")
    docs = c.fetchall()
    
    print(f"Found {len(docs)} extractable docs.")
    
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('GEMINI_API_KEY')
        except:
            pass
            
    if not api_key and not mock:
        print("WARNING: GEMINI_API_KEY not found. Using MOCK mode.")
        mock = True
    
    if not mock and genai:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(config['extraction']['model'])
        
    for (doc_id,) in docs:
        print(f"Processing {doc_id}...")
        
        # 1. Retrieve pages
        pages = retrieve_pages(doc_id, config)
        context_text = "\n---\n".join([f"Page {p['page']}:\n{p['text']}" for p in pages])
        
        extraction_result = None
        
        if mock:
            print("  [MOCK] Generating extractions...")
            extraction_result = get_mock_extraction(doc_id)
            time.sleep(1) # Simulate delay
        else:
            print("  [AI] Calling Gemini...")
            # Construct prompt (Simplified for MVP)
            schema = load_schema('core_extraction.schema.json')
            prompt = f"""
            You are a scientific data extractor. Extract data from the following text based on the provided JSON schema.
            
            CRITICAL VALIDATION RULES (Preflight):
            1. Referential Integrity: Every 'measurement' MUST have a valid 'comparison_id'. Every 'comparison' MUST link to valid 'unit_id', 'scenario_id', 'baseline_condition_id', and 'retrofit_condition_id'.
            2. Uniqueness: All IDs (unit_id, scenario_id, condition_id, comparison_id) MUST be unique.
            3. Roles: Ensure 'baseline' conditions have role='baseline' and 'retrofit' have role='retrofit'.
            4. No Invention: Do NOT invent numerical values. If a value is missing, do not extract the measurement.
            5. Evidence: Every measurement and key entity MUST have a page number evidence.
            
            TEXT:
            {context_text}
            
            SCHEMA:
            {json.dumps(schema)}
            
            Return ONLY valid JSON.
            """
            try:
                response = model.generate_content(prompt)
                # Naive cleanup, ideally use structured output mode if available or robust parser
                json_str = response.text.strip()
                if json_str.startswith('```json'):
                    json_str = json_str[7:-3]
                extraction_result = json.loads(json_str)
            except Exception as e:
                print(f"  Error calling AI: {e}")
                continue
        
        # Save raw result
        os.makedirs('extractions_raw', exist_ok=True)
        with open(os.path.join('extractions_raw', f'{doc_id}.json'), 'w') as f:
            json.dump(extraction_result, f, indent=2)
            
        # Update DB
        c.execute("UPDATE docs SET status = 'extracted_raw' WHERE doc_id = ?", (doc_id,))
        print(f"  Saved to extractions_raw/{doc_id}.json")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mock', action='store_true')
    args = parser.parse_args()
    
    run_extract(mock=args.mock)
