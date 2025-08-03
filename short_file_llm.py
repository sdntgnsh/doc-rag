import asyncio
from typing import List

async def handle_short_document(questions: List[str], doc_url: str = None) -> List[str]:
    """Placeholder function to handle documents with less than 70 pages."""
    # This simulates a different, faster process for short documents.
    # For now, it returns a placeholder answer for each question.
    await asyncio.sleep(0.1) # Simulate a small amount of work
    print(doc_url)
    return [f"Answer from short-document handler for question: '{q}'" for q in questions]