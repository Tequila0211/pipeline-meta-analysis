import os
import hashlib
import pandas as pd
import yaml

def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def index_pdfs():
    with open('run_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    pdf_dir = config.get('pdf_dir', 'pdfs')
    
    if not os.path.exists(pdf_dir):
        print(f"Directory {pdf_dir} does not exist.")
        return

    index_data = []
    
    for filename in os.listdir(pdf_dir):
        if filename.lower().endswith('.pdf'):
            path = os.path.join(pdf_dir, filename)
            doc_hash = calculate_sha256(path)
            
            # For now, we use hash as doc_id
            doc_id = doc_hash
            
            # Placeholder for extracted title (would use PDF library)
            extracted_title = "" 
            
            # Simple filename matching (fallback)
            # In a real scenario we would fuzzy match with manifest title
            
            index_data.append({
                'doc_id': doc_id,
                'pdf_path': path,
                'file_size': os.path.getsize(path),
                'sha256': doc_hash,
                'extracted_title': extracted_title,
                'match_confidence': 0.0,
                'needs_manual_match': True
            })
    
    df = pd.DataFrame(index_data)
    df.to_csv('pdf_index.csv', index=False)
    print(f"Indexed {len(df)} PDFs to pdf_index.csv")

if __name__ == "__main__":
    index_pdfs()
