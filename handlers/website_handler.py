from utils.utils import clean_text, get_text_from_url
from dotenv import load_dotenv
import google.generativeai as genai
import os
import asyncio
from typing import List



load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="""

    1. Provide clear, accurate answers based ONLY on the data given.
    2. Be consise dont explain the answer or say based on the document.



    """
)

async def answer_single_question(question: str, context: str) -> str:


    prompt = f"""
            Here is the scraped website content:
            
            {context}
            
            Based ONLY on the data provided above, answer the following question.
            
            Question: {question}
            Answer:
            """
            
    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config={"temperature": 0.0}
        )
        answer = response.text.strip()
        if not answer:
            answer = "No answer could be generated from the provided content."
        return answer
    except Exception as e:
         answer = f"Error: Could not generate an answer failed after reaching excel {e}"



async def answer_from_website(doc_url,questions: List[str] = None) -> List[str]:


    text_content = get_text_from_url(doc_url)
    answers  = []
    
    for question in questions:
        answer =  await answer_single_question(question, text_content)
        answers.append(answer)


    return answers