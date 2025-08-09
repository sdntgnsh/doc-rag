import requests, os, sys, tempfile, json
from pathlib import Path
from urllib.parse import urlparse, unquote

def download_file(url, filename):
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(filename, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return filename

def convert_with_powerpoint(ppt_path, output_dir):
    import win32com.client
    pdf_path = Path(output_dir) / f"{Path(ppt_path).stem}.pdf"

    ppt = win32com.client.Dispatch("PowerPoint.Application")
    ppt.Visible = True  # MUST be True, otherwise COM will throw

    pres = ppt.Presentations.Open(str(Path(ppt_path).absolute()), WithWindow=False)
    pres.SaveAs(str(pdf_path.absolute()), 32)  # 32 = PDF format
    pres.Close()
    ppt.Quit()

    return str(pdf_path)

def process_query(query):
    if isinstance(query, str):
        query = json.loads(query)

    doc_url = query.get("documents")
    if not doc_url:
        raise ValueError("No 'documents' URL found in query")

    filename = unquote(Path(urlparse(doc_url).path).name)
    if not filename.lower().endswith(('.ppt', '.pptx')):
        filename += '.pptx'

    output_dir = Path(__file__).parent / "converted"
    output_dir.mkdir(exist_ok=True)

    temp_dir = tempfile.mkdtemp()
    ppt_path = Path(temp_dir) / filename

    print(f"Downloading to: {ppt_path}")
    download_file(doc_url, ppt_path)

    if sys.platform != "win32":
        raise EnvironmentError("This method only works on Windows with PowerPoint installed")

    print("Converting with Microsoft PowerPoint...")
    pdf_path = convert_with_powerpoint(ppt_path, output_dir)
    print(f"✓ PDF saved at: {pdf_path}")

    return pdf_path

if __name__ == "__main__":
    sample_query = {
        "documents": "https://hackrx.blob.core.windows.net/assets/Test%20/Test%20Case%20HackRx.pptx?sv=2023-01-03&spr=https&st=2025-08-04T18%3A36%3A56Z&se=2026-08-05T18%3A36%3A00Z&sr=b&sp=r&sig=v3zSJ%2FKW4RhXaNNVTU9KQbX%2Bmo5dDEIzwaBzXCOicJM%3D",
        "questions": []
    }
    process_query(sample_query)
