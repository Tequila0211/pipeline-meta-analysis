# Meta-Analysis AI Pipeline

An automated pipeline for extracting structured scientific data (text/tables) from PDF research papers using Generative AI (Google Gemini) and validating it for meta-analysis.

## 🚀 Features

- **PDF Ingestion**: Automatic indexing and text extraction (OCR agnostic).
- **AI Extraction**: Uses LLMs to extract complex entities (`Units`, `Scenarios`, `Conditions`, `Measurements`) into structured JSON.
- **Strict Validation**: Enforces "Preflight" rules:
    - Referential integrity checks (all IDs must resolve).
    - Uniqueness checks.
    - Evidence traceability (page numbers required).
- **Review Interface**: Streamlit-based UI for manual verification and approval.
- **Concurrent Processing**: The pipeline and UI run independently, sharing a SQLite state database.

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd meta-ana-app
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Setup**:
   Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

## 📋 usage

### 1. Data Preparation
Place your PDF files in the `pdfs/` directory.

### 2. Run the Pipeline
Execute the scripts in order:

```bash
# 1. Index new PDFs
python scripts/02_index_pdfs.py

# 2. Extract text from pages
python scripts/03_pages_text.py

# 3. Triage papers (determine extractability)
python scripts/04_triage.py

# 4. Run AI Extraction (The Heavy Lifting)
python scripts/05_extract.py
# Use --mock for testing without API keys

# 5. Validate Extractions
python scripts/06_validate.py
```

### 3. Review & Approve
Launch the user interface to review extracted data:

```bash
streamlit run app_streamlit.py
```
- Use the sidebar to filter by "Extracted Raw" or "Validated OK".
- Click **"Check for Update"** to see new documents as they are processed.
- Edit JSON directly if needed and click **Approve**.

## 📂 Project Structure

- `scripts/`: Core pipeline logic.
    - `05_extract.py`: AI extraction agent.
    - `06_validate.py`: Strict validation logic.
- `schemas/`: JSON Schemas defining the data structure.
- `extractions_raw/`: Initial AI outputs.
- `state.sqlite`: Local database tracking document status.
- `VALIDATION_GUIDE.md`: Detailed rules for data integrity.

## 🛡️ Validation Rules
The system enforces strict rules defined in `VALIDATION_GUIDE.md`:
- **Uniqueness**: No duplicate IDs for Conditions, Units, etc.
- **Integrity**: Every Measurement must link to a valid Comparison, which must link to valid Scenarios/Conditions.
- **Evidence**: Every extracted item must cite a page number.
