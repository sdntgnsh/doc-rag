# generate_pdf.py
from fpdf import FPDF

# Sample content blocks
LOREM_IPSUM = """
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
"""

PYTHON_CODE_BLOCK = """
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AsyncProcessor:
    def __init__(self, max_workers=5):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def run_in_thread(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, func, *args)

    def shutdown(self):
        self.executor.shutdown(wait=True)

# Example usage:
# processor = AsyncProcessor()
# result = await processor.run_in_thread(time.sleep, 2)
"""

METADATA_SECTION = """
Document Version: 1.7.3
Creation Date: 2025-07-28
Author: RAG Test Suite
Reviewer: AI System
Status: Final
"""

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Large Technical Document for RAG Testing', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_large_pdf(filename="large_document.pdf", target_chunks=750):
    """
    Generates a PDF with enough content to create approximately target_chunks.
    """
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    print(f"Generating PDF with ~{target_chunks} chunks...")

    # Each loop iteration adds 3 chunks (lorem, code, metadata)
    iterations_needed = target_chunks // 3

    for i in range(iterations_needed):
        # Add a text block
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, f"Section {i+1}: Overview\n{LOREM_IPSUM}")
        pdf.ln(5) # Creates space, equivalent to \n\n for chunking

        # Add a code block
        pdf.set_font("Courier", size=9)
        pdf.multi_cell(0, 5, f"Code Snippet {i+1}:\n{PYTHON_CODE_BLOCK}")
        pdf.ln(5)

        # Add a metadata block
        pdf.set_font("Arial", 'I', 8)
        pdf.multi_cell(0, 5, f"Metadata for Section {i+1}:\n{METADATA_SECTION}")
        pdf.ln(10)

        # Add a new page every 5 sections to keep the document structured
        if (i + 1) % 5 == 0:
            pdf.add_page()
            
    pdf.output(filename)
    print(f"Successfully created '{filename}'.")

if __name__ == "__main__":
    create_large_pdf()
