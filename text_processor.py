# text_processor.py
from typing import List

def chunk_text(semantic_chunks: List[str], chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    """
    Takes a list of semantic chunks (paragraphs and tables).
    - Keeps tables as whole chunks.
    - Splits text paragraphs into smaller chunks using character count with overlap.
    """
    final_chunks = []
    
    for chunk in semantic_chunks:
        # If the chunk is a Markdown table, add it as is and continue.
        if chunk.strip().startswith('|'):
            final_chunks.append(chunk)
            continue
            
        # If the chunk is smaller than the chunk_size, just add it.
        if len(chunk) <= chunk_size:
            final_chunks.append(chunk)
            continue

        # Otherwise, split the text chunk with overlap.
        start = 0
        while start < len(chunk):
            end = start + chunk_size
            final_chunks.append(chunk[start:end])
            # Move the start position for the next chunk, creating an overlap
            start += chunk_size - overlap
            # If the next start is past the end of the last chunk, break
            if start >= end:
                break
                
    return [c for c in final_chunks if c.strip()]