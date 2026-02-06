import os
import glob
import yaml
import json
import time
from rank_bm25 import BM25Okapi

def load_pages_text(doc_id):
    """Loads all pages for a doc and returns list of (page_num, text)"""
    files = glob.glob(os.path.join('pages_text', doc_id, 'page_*.txt'))
    pages = []
    for f in files:
        # Extract page number from filename page_001.txt
        try:
            basename = os.path.basename(f)
            page_num = int(basename.replace('page_', '').replace('.txt', ''))
            with open(f, 'r', encoding='utf-8') as tf:
                text = tf.read()
            pages.append({'page': page_num, 'text': text})
        except:
            continue
    return sorted(pages, key=lambda x: x['page'])

def retrieve_pages(doc_id, config):
    pages = load_pages_text(doc_id)
    if not pages:
        return []
    
    corpus = [p['text'] for p in pages]
    tokenized_corpus = [doc.split(" ") for doc in corpus]
    
    bm25 = BM25Okapi(tokenized_corpus)
    
    queries = config.get('rag', {}).get('query_templates', [])
    top_k = config.get('rag', {}).get('bm25_top_k_pages', 15)
    
    all_scores = {} # page_idx -> max_score
    
    for query in queries:
        tokenized_query = query.split(" ")
        doc_scores = bm25.get_scores(tokenized_query)
        
        for i, score in enumerate(doc_scores):
            if i not in all_scores:
                all_scores[i] = 0
            if score > all_scores[i]:
                all_scores[i] = score
                
    # Sort pages by score
    sorted_indices = sorted(all_scores, key=all_scores.get, reverse=True)
    
    selected_indices = sorted_indices[:top_k]
    selected_pages = [pages[i] for i in selected_indices if i < len(pages)]
    
    # Save retrieval metadata
    snippets_dir = os.path.join('snippets', doc_id)
    os.makedirs(snippets_dir, exist_ok=True)
    
    meta = {
        'doc_id': doc_id,
        'selected_pages': [p['page'] for p in selected_pages],
        'timestamp': time.time()
    }
    
    with open(os.path.join(snippets_dir, f'retrieval_{int(time.time())}.json'), 'w') as f:
        json.dump(meta, f, indent=2)
        
    return selected_pages
