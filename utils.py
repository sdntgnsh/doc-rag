import markdown
from bs4 import BeautifulSoup
import codecs
import re

import html

def clean_text(raw_text: str) -> str:
    """
    Cleans a string by removing common formatting artifacts.

    This function performs the following actions:
    1. Decodes Unicode escape sequences (e.g., '\\u2019' -> '’').
    2. Handles standard C-style backslash escapes (e.g., '\\"' -> '"', '\\n' -> newline).
    3. Unescapes HTML entities (e.g., '&amp;' -> '&', '&quot;' -> '"').
    4. Normalizes whitespace by replacing multiple spaces/tabs/newlines with a single space.
    5. Strips any leading or trailing whitespace from the final text.

    Args:
        raw_text: The input string with formatting artifacts.

    Returns:
        A cleaned, more readable version of the string.
    """
    # Step 1 & 2: Use codecs to handle backslash escape sequences like \" and \n
    # The 'unicode_escape' codec interprets backslashed characters correctly.
    try:
        # We encode to raw_unicode_escape first to preserve existing unicode characters,
        # then decode with unicode_escape to process the slashes.
        decoded_text = codecs.decode(raw_text, 'unicode_escape')
    except Exception as e:
        print(f"Could not decode escape sequences: {e}")
        decoded_text = raw_text


    # Step 3: Unescape HTML entities like &amp; or &quot;
    unscaped_text = html.unescape(decoded_text)

    # Step 4: Normalize whitespace. This replaces sequences of one or more
    # whitespace characters (spaces, tabs, newlines) with a single space.
    normalized_text = re.sub(r'\s+', ' ', unscaped_text)

    # Step 5: Remove any leading or trailing whitespace
    cleaned_text = normalized_text.strip()

    return cleaned_text

def clean_markdown(md_text):
    """
    Converts a Markdown string to a single, clean line of text.
    
    This function performs a 3-step process:
    1. Converts the Markdown input into HTML.
    2. Uses BeautifulSoup to strip all HTML tags, leaving only the text.
    3. Normalizes all whitespace (newlines, etc.) into single spaces.
    
    Args:
        md_text: A string containing text with Markdown formatting.

    Returns:
        A clean, normalized string with no Markdown or HTML formatting.
    """
    # Defensive check for non-string input
    if not isinstance(md_text, str):
        return ""
        
    # Step 1: Convert Markdown to HTML
    html = markdown.markdown(md_text)
    
    # Step 2: Strip HTML tags to get plain text
    # We use a space as a separator to ensure words don't run together
    soup = BeautifulSoup(html, "html.parser")
    plain_text = soup.get_text(separator=' ')
    
    # Step 3: Handle potential escape characters and normalize whitespace
    # This combines the logic from your advanced_text_cleaner
    unscaped_text = codecs.decode(plain_text, 'unicode_escape')
    normalized_whitespace = re.sub(r'\s+', ' ', unscaped_text).strip()
    normalized_whitespace = normalized_whitespace.replace('*', ' ')
    
    return clean_text(normalized_whitespace)


if __name__ == "__main__":
   
    text = """"Based on the policy, the claim is admissible. **Admissibility:** 1. **Dependent Eligibility:** Children over 18 and up to the age of 26 are covered, provided they are unmarried, unemployed, and dependent. 2. **Dental Exclusion:** Dental surgery is covered when it is necessitated by an accident and requires a minimum of 24 hours of hospitalization. **Claim Process:** 1. **Notification:** You must notify the TPA within 24 hours of the emergency hospitalization or before discharge, whichever is earlier. 2. **Procedure:** You can opt for a cashless facility at a network hospital (which requires pre-authorization) or get treatment at a non-network hospital and file for reimbursement. 3. **Required Documents for Reimbursement:** The claim must be supported by the following original documents and submitted within 15 days of discharge: * Duly completed claim form * Photo ID and Age proof * Health Card, policy copy, and KYC documents * Attending medical practitioner's/surgeon's certificate regarding the diagnosis/nature of the operation performed, with the date of diagnosis and investigation reports * Medical history of the patient, including all previous consultation papers * Bills (with a detailed breakup) and payment receipts * Discharge certificate/summary from the hospital * Original final hospital bill with a detailed break-up and all original deposit and final payment receipts * Original invoice with payment receipt and implant stickers for any implants used * All original diagnostic reports (imaging and laboratory) with the practitioner's prescription and invoice/bill * All original medicine/pharmacy bills with the practitioner's prescription * MLC / FIR copy, as this is an accidental case * Pre and post-operative imaging reports * Copy of indoor case papers with nursing sheet detailing medical history, treatment, and progress * A cheque copy with the proposer's name printed, or a copy of the first page of the bank passbook/statement (not older than 3 months)
    """


    print(clean_markdown(text))