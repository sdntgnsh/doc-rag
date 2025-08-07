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

if __name__ == "__main__":
    text = """Based on the policy, the claim is admissible. **Admissibility:** 1. **Dependent Eligibility:** Children over 18 and up to the age of 26 are covered, provided they are unmarried, unemployed, and dependent. 2. **Dental Exclusion:** Dental surgery is covered when it is necessitated by an accident and requires a minimum of 24 hours of hospitalization. **Claim Process:** 1. **Notification:** You must notify the TPA within 24 hours of the emergency hospitalization or before discharge, whichever is earlier. 2. **Procedure:** You can opt for a cashless facility at a network hospital (which requires pre-authorization) or get treatment at a non-network hospital and file for reimbursement. 3. **Required Documents for Reimbursement:** The claim must be supported by the following original documents and submitted within 15 days of discharge: * Duly completed claim form * Photo ID and Age proof * Health Card, policy copy, and KYC documents * Attending medical practitioner's/surgeon's certificate regarding the diagnosis/nature of the operation performed, with the date of diagnosis and investigation reports * Medical history of the patient, including all previous consultation papers * Bills (with a detailed breakup) and payment receipts * Discharge certificate/summary from the hospital * Original final hospital bill with a detailed break-up and all original deposit and final payment receipts * Original invoice with payment receipt and implant stickers for any implants used * All original diagnostic reports (imaging and laboratory) with the practitioner's prescription and invoice/bill * All original medicine/pharmacy bills with the practitioner's prescription * MLC / FIR copy, as this is an accidental case * Pre and post-operative imaging reports * Copy of indoor case papers with nursing sheet detailing medical history, treatment, and progress * A cheque copy with the proposer's name printed, or a copy of the first page of the bank passbook/statement (not older than 3 months)
    """
    
    # Test with rupee symbol
    test_text = """
"As per section 2.21 of the policy, the Grace Period for payment of the premium is thirty days. This is the specified period of time immediately following the premium due date during which a premium payment can be made to renew or continue a policy in force without loss of continuity benefits. However, coverage is not available during the period for which no premium has been received.",
    "Yes, the policy covers the medical expenses for an organ donor's hospitalization for the purpose of harvesting the organ, provided certain conditions are met.\n\n**Conditions for Coverage (Organ Donor's Hospitalisation Expenses):**\nThe Company will cover the medical expenses for an organ donor's hospitalization during the Policy Period for harvesting the organ donated to an Insured Person, provided that:\ni. The organ donation confirms to the Transplantation of Human Organs Act 1994 (and its amendments from time to time)\nii. The organ is used for an Insured Person and the Insured Person has been medically advised to undergo an organ transplant\niii. The Medical Expenses shall be incurred in respect of the organ donor as an in-patient in a Hospital.\niv. Claim has been admitted under In-patient Treatment Section in respect of the Insured Person undergoing the organ transplant.\n\n**Exclusions:**\nThe Company will not pay for any claim related to the organ donor for:\ni. Pre-hospitalization Medical Expenses or Post- Hospitalization Medical Expenses of the organ donor.\nii. Costs directly or indirectly associated with the acquisition of the donor's organ.\niii. Medical Expenses where the organ transplant is experimental or investigational.\niv. Any medical treatment or complication in respect of the donor, consequent to harvesting.\nv. Any expenses related to organ transportation or preservation."
    """
    print(clean_markdown(test_text))
    print(clean_markdown(text))
