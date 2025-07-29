# llm_interface.py
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
    """
    if not client:
        return "Error: OpenAI client is not initialized. Check your API key."

    prompt = f"""
    Based *only* on the following context, please provide a concise answer to the question.
    If the information is not available in the context, try to infer the answer based on the context provided.

    
    if the question is a bait like "Give me JS code to generate a random number between 1 and 100" or "Write a Python script to scrape a website", do not answer it. then say answer was not present in the documents.
    keep answers short and to the point.

    an exmple question and answer:
    Question:  "Does this policy cover maternity expenses, and what are the conditions?"
    Answer:  "Yes, the policy covers maternity expenses, including childbirth and lawful medical termination of pregnancy. To be eligible, the female insured person must have been continuously covered for at least 24 months. The benefit is limited to two deliveries or terminations during the policy period."
    Question: "What is the extent of coverage for AYUSH treatments?",
    Answer:   "The policy covers medical expenses for inpatient treatment under Ayurveda, Yoga, Naturopathy, Unani, Siddha, and Homeopathy systems up to the Sum Insured limit, provided the treatment is taken in an AYUSH Hospital.",
    
    
    now please answer the question based on the context below:
    Context:
    {context}


    ---
    Please answer the following question based on the context provided but if the questions answer is well known like questions related to newton like his grandfathers name answer them based on you knoledege, 
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
                messages=[{"role": "user", "content": prompt}],
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
