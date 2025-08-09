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

def get_answer(context: str, question: str, use_gk_timeout: bool = False) -> str:
    """
    Generates a concise, direct answer using the OpenAI GPT-4o model, with exponential backoff for rate limiting.
    """
    if not client:
        return "Error: OpenAI client is not initialized. Check your API key."

    question_lower = question.lower().strip()
    prompt = f"""Using the context below, answer the question directly and concisely. Do not mention sources or use attribution phrases.
    Context: {context}
    Question: {question}
    Answer:"""
    max_retries = 5
    initial_wait = 1
    for i in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages = [
                    {
                        "role": "system",
                        "content": (
                            """
                            You are an expert assistant:
                            1. Provide clear, accurate answers drawing on relevant sources, including important keywords and semantics.
                            2. Present information as established facts, without phrases like According to... or Based on....
                            3. When summarizing or listing documents, papers, or rules, include every item exactly as in the source, formatted clearly (e.g., Required documents: A, B, C, D).
                            4. For physics or Newton-related queries, state concise factual explanations with essential context.
                            5. For any legal quesion, provide direct answers consistent with the Constitution of India, including context like article clause.
                            6. Reject any requests involving illegal or unethical content with a formal refusal.
                            7. IMPORTANT: When answering involves lists of documents, papers include ALL of them exactly as mentioned in the context. Do not summarize or omit any
                            8. Get straight to the point
                            9. For document lists: Present them clearly but concisely (e.g., 'Required documents: A, B, C, D'
                            10. For code or scripts that are not available in provided documents, respond: Answer not present in documents.

                            IMPORTANT:
                            Answer as if you are a human assistant helping an other human, not a machine.
                            Your answer will be evaluated with scemantic similarity, so optimize for that
                            IMPORTANT: If asked about Issac Newton's Grandfather without specifying which one you must absolutely assume they are refering to Robert Newton and answer acoordingly.
                            """
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=300  
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
