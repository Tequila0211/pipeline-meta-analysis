import os
import json
import pandas as pd
import pdfplumber
import yaml
import time

def extract_pages_text():
    with open('run_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Load index to get doc_ids
    if not os.path.exists('pdf_index.csv'):
        print("pdf_index.csv not found. Run 02_index_pdfs.py first.")
        return
        
    df = pd.read_csv('pdf_index.csv')
    
    pages_text_dir = 'pages_text'
    os.makedirs(pages_text_dir, exist_ok=True)
    
    for _, row in df.iterrows():
        doc_id = row['doc_id']
        pdf_path = row['pdf_path']
        
        doc_dir = os.path.join(pages_text_dir, doc_id)
        os.makedirs(doc_dir, exist_ok=True)
        
        # Check if already processed (simple idempotency)
        if os.path.exists(os.path.join(doc_dir, 'pages_meta.json')):
            print(f"Skipping {doc_id} (already extracted)")
            continue
            
        print(f"Extracting {pdf_path}...")
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                num_pages = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    
                    # Save page text
                    page_filename = f"page_{i:03d}.txt"
                    with open(os.path.join(doc_dir, page_filename), 'w', encoding='utf-8') as f_text:
                        f_text.write(text)
                
                # Save metadata
                meta = {
                    'num_pages': num_pages,
                    'tool': 'pdfplumber',
                    'timestamp': time.time()
                }
                with open(os.path.join(doc_dir, 'pages_meta.json'), 'w') as f_meta:
                    json.dump(meta, f_meta, indent=2)
                    
        except Exception as e:
            print(f"Error extraction {doc_id}: {e}")

if __name__ == "__main__":
    extract_pages_text()
