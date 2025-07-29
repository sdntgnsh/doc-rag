# query_expander.py
import requests
import json
from typing import List
import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

class QueryExpander:
    """
    Uses Google's Gemini Flash model to expand a single user query into multiple variations
    to improve the initial document retrieval process.
    """
    def expand(self, query: str) -> List[str]:
        """
        Generates variations of the user's query using the Gemini API.

        Returns:
            A list of questions, including the original.
        """
        # The API key is handled by the execution environment.
        api_key = os.getenv("GEMINI_API_KEY")
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

        # A specific prompt designed to ask the LLM for query variations.
        prompt = f"""
        Based on the following user question, generate 3 additional, different ways of asking the same thing.
        The goal is to improve document retrieval for a RAG system.

        Original Question: "{query}"
        """

        # Construct the payload for structured JSON output
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "ARRAY",
                    "description": "A list of 3 rephrased questions.",
                    "items": {
                        "type": "STRING"
                    }
                }
            }
        }

        try:
            response = requests.post(
                api_url,
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=15  # Set a reasonable timeout
            )
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            
            result = response.json()
            
            # Safely extract the JSON text from the Gemini API response
            if (
                result.get("candidates") and
                result["candidates"][0].get("content") and
                result["candidates"][0]["content"].get("parts")
            ):
                json_text = result["candidates"][0]["content"]["parts"][0]["text"]
                expanded_queries = json.loads(json_text)

                if isinstance(expanded_queries, list):
                    # Add the original query to the list to ensure it's always included
                    all_queries = [query] + expanded_queries
                    print(f"Expanded query into: {all_queries}")
                    return all_queries
            else:
                 print("Gemini API response did not have the expected structure. Using original query only.")

        except requests.exceptions.RequestException as e:
            print(f"API request failed for query expansion: {e}. Using original query only.")
        except (json.JSONDecodeError, TypeError, KeyError, IndexError) as e:
            print(f"Could not parse query expansion response from Gemini: {e}. Using original query only.")
        
        # Fallback to using only the original query if expansion fails
        return [query]
