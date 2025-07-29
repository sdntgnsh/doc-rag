# document_loader.py
import fitz
import requests
import io
from typing import List, Tuple

def _get_gdrive_download_url(url: str) -> str:
    if "drive.google.com" in url and "/view" in url:
        try:
            file_id = url.split('/d/')[1].split('/')[0]
            return f'https://drive.google.com/uc?export=download&id={file_id}'
        except IndexError:
            return url
    return url

def _table_to_markdown(table_data: list) -> str:
    markdown_str = ""
    header = [str(cell) if cell is not None else "" for cell in table_data[0]]
    markdown_str += "| " + " | ".join(header) + " |\n"
    markdown_str += "| " + " | ".join(["---"] * len(header)) + " |\n"
    for row in table_data[1:]:
        row_data = [str(cell) if cell is not None else "" for cell in row]
        markdown_str += "| " + " | ".join(row_data) + " |\n"
    return markdown_str

def _process_page_content(page: fitz.Page) -> List[str]:
    try:
        page_chunks = []
        tables = page.find_tables()
        table_bboxes = [fitz.Rect(t.bbox) for t in tables]
        
        text_blocks = [block[4].strip() for block in page.get_text("blocks") if not any(fitz.Rect(block[:4]).intersects(tb) for tb in table_bboxes)]
        
        if text_blocks:
            page_chunks.extend(text_blocks)
        
        for table in tables:
            if table.row_count > 0 and (table_data := table.extract()):
                page_chunks.append(_table_to_markdown(table_data))
                
        return [chunk for chunk in page_chunks if chunk]
    except Exception as e:
        print(f"Warning: Could not process page {page.number}. Error: {e}. Skipping page.")
        return []

def get_chunks_from_content(pdf_content: bytes) -> List[str]:
    """Processes a PDF from a byte stream and returns its text chunks."""
    doc = fitz.open(stream=io.BytesIO(pdf_content), filetype="pdf")
    all_chunks = []
    for page in doc:
        all_chunks.extend(_process_page_content(page))
    return all_chunks

def get_cache_key_from_content(pdf_content: bytes) -> Tuple[int, str]:
    """
    Generates a unique cache key for a PDF based on page count and first word.
    """
    doc = fitz.open(stream=io.BytesIO(pdf_content), filetype="pdf")
    page_count = doc.page_count
    first_word = ""
    if page_count > 0:
        first_page_text = doc[0].get_text("text")
        if first_page_text:
            first_word = first_page_text.strip().split()[0]
    return (page_count, first_word)

def download_pdf_content(url: str) -> bytes | None:
    """Downloads the raw content of a PDF from a URL."""
    try:
        download_url = _get_gdrive_download_url(url)
        response = requests.get(download_url, timeout=20)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"Error fetching document from URL {url}: {e}")
        return None
