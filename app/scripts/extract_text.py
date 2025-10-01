import pdfplumber

def extract_pdf_text(pdf_path: str):
    with pdfplumber.open(pdf_path) as pdf:
        lines = []
        for p_idx, page in enumerate(pdf.pages, start=1):
            content = page.extract_text() or ""
            line_no = 0
            for line in content.split("\n"):
                clean = line.strip()
                if clean:
                    line_no += 1
                    lines.append({
                        "text": clean,
                        "page": p_idx,
                        "line": line_no
                    })
    return lines
