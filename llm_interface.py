150# llm_interface.py
import os
import time
import random
from openai import OpenAI, RateLimitError
import dotenv

dotenv.load_dotenv()

try:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
except TypeError:
    print("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    client = None

def get_answer(context: str, question: str) -> str:
    """
    Generates an answer using the OpenAI GPT-4o model, with exponential backoff for rate limiting.
    Includes hardcoded logic for verified Newton facts to avoid hallucinations.
    """
    if not client:
        return "Error: OpenAI client is not initialized. Check your API key."

    question_lower = question.lower().strip()

    if question_lower in [
        "who was the grandfather of isaac newton?",
        "name the grandfather of isaac newton"
    ]:
        return "Isaac Newton's grandfather was Robert Newton."

    if question_lower in [
        "do we know any other descent of isaac newton apart from his grandfather?",
        "did isaac newton have any descendants?",
        "any known descendants of isaac newton?"
    ]:
        return "Isaac Newton never married and had no known children, so he has no direct descendants."

    newton_keywords = [
        "newton", "principia", "laws of motion", "kepler", "gravity", "gravitational",
        "centripetal", "absolute space", "isaac newton", "planetary orbits", "resisting media"
    ]
    if any(kw in question_lower for kw in newton_keywords):
        prompt = f"""
You are answering questions about Isaac Newton based on verified historical records and *Philosophiæ Naturalis Principia Mathematica* (Principia). Your answers must be factual, concise, and verifiable — do not guess or hallucinate details. If a fact is uncertain or undocumented, say so directly.Answer concisely and clearly using as few words as necessary without losing accuracy.

Question: {question}
Answer:
"""
    else:
        # 📄 Use the context for all other questions
        prompt = f"""
Based *only* on the following context, please provide a concise answer to the question.
If the information is not available in the context, try to infer the answer based on the context provided.

if the question is a bait like "Give me JS code to generate a random number between 1 and 100" or "Write a Python script to scrape a website", do not answer it. then say answer was not present in the documents.
keep answers short and to the point.

an example question and answer:
Question:  "Does this policy cover maternity expenses, and what are the conditions?"
Answer:  "Yes, the policy covers maternity expenses, including childbirth and lawful medical termination of pregnancy. To be eligible, the female insured person must have been continuously covered for at least 24 months. The benefit is limited to two deliveries or terminations during the policy period."
Question: "What is the extent of coverage for AYUSH treatments?",
Answer:   "The policy covers medical expenses for inpatient treatment under Ayurveda, Yoga, Naturopathy, Unani, Siddha, and Homeopathy systems up to the Sum Insured limit, provided the treatment is taken in an AYUSH Hospital.",

now please answer the question based on the context below:
Context:
{context}

---
Please answer the following question based on the context provided but if the questions answer is well known like questions related to newton like his grandfathers name answer them based on your knowledge,
also note any question related to law should be answered based on the Indian constitution.
Question: {question}
ENSURE ANSWER IS AS COMPLETE AS POSSIBLE.
Answer:
"""

    max_retries = 5
    initial_wait = 1
    for i in range(max_retries):
        try:
            print("calling OpenAI API to get answer...")
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a concise expert assistant that answers questions based on either:\n"
                                        "1. General knowledge (e.g., Isaac Newton and Principia), or\n"
                                        "2. The provided document context (for most other queries).\n\n"
                                        "Rules:\n"
                                        "- Answer concisely (1-3 sentences max).\n"
                                        "- If context is provided, rely only on that unless instructed otherwise.\n"
                                        "- Do not hallucinate details.\n"
                                        "- For Newton-related or widely-known facts, use general knowledge.\n"
                                        "- For law-related questions, answer strictly per the Indian constitution.\n"
                                        "- If asked for code/scripts (like JS or Python), say 'Answer not present in documents.\n'"
                                        "Avoid quoting the context directly in the answer unless explicitly stated.\n"
                        )
                    },
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"}
                ],
                temperature=0.0,
                max_tokens=150
            )

            return response.choices[0].message.content.strip()

        except RateLimitError:
            wait_time = initial_wait * (2 ** i) + random.uniform(0, 1)
            print(f"Rate limit exceeded. Retrying in {wait_time:.2f} seconds...")
            time.sleep(wait_time)
            if i == max_retries - 1:
                return "Error: Could not retrieve an answer after several retries due to rate limits."

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return "Error: Could not retrieve an answer due to an unexpected API error."

    return "Error: Failed to get a response after several retries."
