import asyncio
import os
import json
import requests
import io
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI
from PyPDF2 import PdfReader  # Requires pip install pypdf2

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def extract_pdf_text(url: str) -> str:
    """Downloads the PDF from the URL and extracts its text content."""
    try:
        print(f"[DEBUG] Downloading PDF from {url}")
        response = requests.get(url)
        response.raise_for_status()
        pdf_file = io.BytesIO(response.content)
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        print("[DEBUG] PDF text extracted successfully.")
        return text
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

tools = [
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Make a GET request to a URL and retrieve the JSON response.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch."},
                },
                "required": ["url"],
            },
        },
    },
]

async def http_get(url: str) -> Dict:
    """Tool function to perform a GET request and return JSON or error."""
    try:
        response = await asyncio.to_thread(requests.get, url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

available_tools = {"http_get": http_get}

async def run_agent(messages: List[Dict[str, Any]]) -> str:
    """Runs the agent loop with tool calling until a final answer is reached."""
    while True:
        response = await client.chat.completions.create(
            model="gpt-4o",  # Use a capable model like gpt-4o or gpt-4-turbo
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        if message.tool_calls:
            messages.append({"role": message.role, "content": message.content, "tool_calls": message.tool_calls})
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                func = available_tools.get(func_name)
                if not func:
                    result = {"error": f"Tool {func_name} not found."}
                else:
                    result = await func(**args)
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": json.dumps(result),
                })
        else:
            return message.content

async def handle_flight_query(doc_url: str) -> List[str]:
    """
    Generalized handler that uses an LLM to parse the PDF, understand instructions,
    and execute steps dynamically using tool calls.
    """
    print(f"[DEBUG] Starting generalized query handler with doc_url: {doc_url}")
    
    pdf_text = await extract_pdf_text(doc_url)
    if not pdf_text:
        return ["Could not extract text from the PDF."]
    
    system_prompt = """
You are an intelligent agent tasked with following the instructions in the provided document to compute and return the final result.
The document may contain rules, mappings (e.g., tables of cities to landmarks), URLs for APIs, and step-by-step procedures.
Analyze the document content, extract necessary information like mappings and URLs, and use the available tools to fetch data as needed.
Reason step by step, and when you have the final answer (e.g., a flight number), output it directly in the format specified in the document, such as "Flight number: XXX".
Do not output intermediate steps in the final message; only the final result.

Document content:
{pdf_text}
""".format(pdf_text=pdf_text)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Execute the task as described in the document and provide the final result."}
    ]
    
    result = await run_agent(messages)
    print(f"[DEBUG] Final result: {result}")
    return [result]