import markdown
from bs4 import BeautifulSoup
import re
import html
import unicodedata
import sys

# Ensure stdout uses UTF-8 encoding to handle special characters like ₹
sys.stdout.reconfigure(encoding='utf-8')

def clean_text(raw_text: str) -> str:
    """
    Cleans a string by removing common formatting artifacts.

    This function performs the following actions:
    1. Ensures the input is a string and decodes bytes if necessary.
    2. Unescapes HTML entities (e.g., '&amp;' -> '&', '&quot;' -> '"').
    3. Normalizes Unicode characters to their canonical form (e.g., handles rupee symbol).
    4. Normalizes whitespace by replacing multiple spaces/tabs/newlines with a single space.
    5. Strips any leading or trailing whitespace from the final text.

    Args:
        raw_text: The input string or bytes with formatting artifacts.

    Returns:
        A cleaned, more readable version of the string.
    """
    # Handle case where input might be bytes
    if isinstance(raw_text, bytes):
        try:
            raw_text = raw_text.decode('utf-8')
        except UnicodeDecodeError:
            raw_text = raw_text.decode('latin1', errors='replace')

    # Step 1: Unescape HTML entities like &amp; or &quot;
    unescaped_text = html.unescape(raw_text)

    # Step 2: Normalize Unicode characters to NFC form to handle characters like ₹
    normalized_text = unicodedata.normalize('NFC', unescaped_text)

    # Step 3: Normalize whitespace (replace multiple spaces, tabs, newlines with a single space)
    cleaned_text = re.sub(r'\s+', ' ', normalized_text)

    # Step 4: Remove any leading or trailing whitespace
    return cleaned_text.strip()

def clean_markdown(md_text):
    """
    Converts a Markdown string to a single, clean line of text.
    
    This function performs a 3-step process:
    1. Converts the Markdown input into HTML.
    2. Uses BeautifulSoup to strip all HTML tags, leaving only the text.
    3. Normalizes all whitespace (newlines, etc.) into single spaces and cleans the text.
    
    Args:
        md_text: A string containing text with Markdown formatting.

    Returns:
        A clean, normalized string with no Markdown or HTML formatting.
    """
    # Defensive check for non-string input
    if not isinstance(md_text, str):
        return ""
        
    # Step 1: Convert Markdown to HTML
    html_text = markdown.markdown(md_text)
    
    # Step 2: Strip HTML tags to get plain text
    soup = BeautifulSoup(html_text, "html.parser")
    plain_text = soup.get_text(separator=' ')
    
    # Step 3: Clean the text (handles HTML entities, Unicode, and whitespace)
    cleaned_text = clean_text(plain_text).replace('*', ' ')
    normalized_spacing = cleaned_text.split()

    cleaned_text = ' '.join(normalized_spacing).strip()
    return cleaned_text


import requests
from bs4 import BeautifulSoup

def get_text_from_url(url):
    """
    Fetches the content from a URL and extracts all the text.

    This function sends an HTTP GET request to the specified URL,
    parses the HTML content of the page, and extracts all the visible
    text, stripping out HTML tags, scripts, and styles.

    Args:
        url (str): The URL of the website to scrape.

    Returns:
        str: The extracted text content from the webpage.
             Returns an error message string if the request fails or
             if the content cannot be parsed.
    """
    try:
        # Send an HTTP GET request to the URL.
        # The headers are used to mimic a browser visit.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)

        # Raise an exception for bad status codes (4xx or 5xx).
        response.raise_for_status()

        # Use BeautifulSoup to parse the HTML content.
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script and style elements, as they don't contain useful text.
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()

        # Get all the text from the parsed HTML.
        # The .get_text() method returns all the text in a document
        # or beneath a tag, as a single Unicode string.
        # The 'strip=True' argument removes leading/trailing whitespace.
        # The 'separator=" "' argument adds a space between text elements.
        text = soup.get_text(separator=' ', strip=True)

        return text

    except requests.exceptions.RequestException as e:
        # Handle potential network errors (e.g., DNS failure, refused connection).
        return f"Error: Could not retrieve the URL. {e}"
    except Exception as e:
        # Handle other potential exceptions.
        return f"An unexpected error occurred: {e}"
    

from urllib.parse import urlparse
import os


def is_file_url(url):
    """
    Checks if a URL likely points to a file by inspecting the path for a file extension.
    """
    try:
        # A list of common file extensions. You can expand this list.
        file_extensions = [
            '.pdf', '.docx', '.xlsx', '.pptx', '.zip', '.rar', '.7z',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',
            '.mp3', '.wav', '.ogg',
            '.mp4', '.avi', '.mov', '.wmv',
            '.json', '.xml', '.csv', '.txt', '.rtf',
            '.bin', '.iso', '.exe', '.dll'
        ]

        # Parse the URL to get its components
        parsed_url = urlparse(url)
        # Get the path from the parsed URL
        path = parsed_url.path

        # Get the file extension from the path
        _, extension = os.path.splitext(path)

        if extension.lower() in file_extensions:
            return True
        else:
            return False

    except Exception as e:
        print(f"An error occurred: {e}")
        return False


if __name__ == "__main__":
    text = """Based on the policy, the claim is admissible. **Admissibility:** 1. **Dependent Eligibility:** Children over 18 and up to the age of 26 are covered, provided they are unmarried, unemployed, and dependent. 2. **Dental Exclusion:** Dental surgery is covered when it is necessitated by an accident and requires a minimum of 24 hours of hospitalization. **Claim Process:** 1. **Notification:** You must notify the TPA within 24 hours of the emergency hospitalization or before discharge, whichever is earlier. 2. **Procedure:** You can opt for a cashless facility at a network hospital (which requires pre-authorization) or get treatment at a non-network hospital and file for reimbursement. 3. **Required Documents for Reimbursement:** The claim must be supported by the following original documents and submitted within 15 days of discharge: * Duly completed claim form * Photo ID and Age proof * Health Card, policy copy, and KYC documents * Attending medical practitioner's/surgeon's certificate regarding the diagnosis/nature of the operation performed, with the date of diagnosis and investigation reports * Medical history of the patient, including all previous consultation papers * Bills (with a detailed breakup) and payment receipts * Discharge certificate/summary from the hospital * Original final hospital bill with a detailed break-up and all original deposit and final payment receipts * Original invoice with payment receipt and implant stickers for any implants used * All original diagnostic reports (imaging and laboratory) with the practitioner's prescription and invoice/bill * All original medicine/pharmacy bills with the practitioner's prescription * MLC / FIR copy, as this is an accidental case * Pre and post-operative imaging reports * Copy of indoor case papers with nursing sheet detailing medical history, treatment, and progress * A cheque copy with the proposer's name printed, or a copy of the first page of the bank passbook/statement (not older than 3 months)
    """
    
    file_url = "https://hackrx.blob.core.windows.net/assets/Arogya%20Sanjeevani%20Policy%20-%20CIN%20-%20U10200WB1906GOI001713%201.pdf?sv=2023-01-03&st=2025-07-21T08%3A29%3A02Z&se=2025-09-22T08%3A29%3A00Z&sr=b&sp=r&sig=nzrz1K9Iurt%2BBXom%2FB%2BMPTFMFP3PRnIvEsipAX10Ig4%3D"
    print(f"Is '{file_url}' a file? {is_file_url(file_url)}")

    # This is a website URL
    website_url = "https://register.hackrx.in/utils/get-secret-token?hackTeam=4366"
    print(f"Is '{website_url}' a file? {is_file_url(website_url)}")
