import os
import pandas as pd
from fpdf import FPDF

def create_mock_manifest():
    data = {
        'DT': ['ARTICLE', 'ARTICLE', 'REVIEW'],
        'TI': ['Passive cooling in residential buildings', 'Retrofit strategies for schools', 'Review of cooling technologies'],
        'AU': ['Smith, J.', 'Doe, A.', 'Brown, B.'],
        'PY': [2024, 2023, 2022],
        'SO': ['Energy & Buildings', 'Building Environment', 'Renewable Energy'],
        'DI': ['10.1016/j.enbuild.2024.01', '10.1016/j.buildenv.2023.05', '10.1016/j.renene.2022.09']
    }
    df = pd.DataFrame(data)
    df.to_excel('manifest.xlsx', index=False)
    print("Created manifest.xlsx")

def create_mock_pdf(filename, content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, content)
    os.makedirs('pdfs', exist_ok=True)
    pdf.output(os.path.join('pdfs', filename))
    print(f"Created pdfs/{filename}")

def main():
    create_mock_manifest()
    
    # PDF 1 matches first article
    content1 = """
    Passive cooling in residential buildings.
    Smith, J., 2024.
    
    Baseline U-value was 2.0 W/m2K. After retrofit, U-value is 0.5 W/m2K.
    Overheating hours (TM52) reduced from 500h to 100h.
    """
    create_mock_pdf("Smith_2024.pdf", content1)
    
    # PDF 2 matches second article
    content2 = """
    Retrofit strategies for schools.
    Doe, A., 2023.
    
    We compared natural ventilation vs mechanical cooling.
    Baseline temperature max: 35C. Retrofit temperature max: 28C.
    Outcomes: Operative temperature (Outcome B).
    """
    create_mock_pdf("Doe_2023.pdf", content2)
    
    # PDF 3 is a review (should be excluded)
    content3 = """
    Review of cooling technologies.
    Brown, B., 2022.
    
    This is a review of multiple studies. We found that shading is effective.
    """
    create_mock_pdf("Brown_2022.pdf", content3)

if __name__ == "__main__":
    main()
