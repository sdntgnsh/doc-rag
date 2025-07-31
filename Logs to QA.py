import json  # Use json for parsing JSON data
from urllib.parse import unquote, urlparse
import os # For checking file existence
import re # Import regex module (though not strictly used in the final raw_decode approach, good to keep for potential debugging)

def extract_filename_from_url(url):
    """
    Extracts and decodes the filename from a given URL.

    Args:
        url (str): The URL string from which to extract the filename.

    Returns:
        str: The decoded filename.
    """
    path = urlparse(url).path
    return unquote(path.split('/')[-1])

# Define input and output file paths
# IMPORTANT: Replace 'your_input_file.jsonl' with the actual path to your JSONL file.
# For example: input_file = r"C:\Users\YourUser\Documents\my_logs.jsonl"
input_file = "logs.jsonl" # <--- **CHANGE THIS TO YOUR ACTUAL INPUT FILE PATH**
output_file = "output.txt"

print(f"Attempting to process '{input_file}' and save output to '{output_file}'...")

try:
    # Check if the input file exists before attempting to open it
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"The input file '{input_file}' does not exist.")

    # Read the entire file content into a single string
    with open(input_file, "r", encoding="utf-8") as f:
        full_content = f.read()

    parsed_entries = []
    decoder = json.JSONDecoder()
    idx = 0
    # Iterate through the full content to find and decode JSON objects
    while idx < len(full_content):
        # Skip any leading whitespace or non-JSON characters
        while idx < len(full_content) and full_content[idx].isspace():
            idx += 1
        if idx >= len(full_content): # Reached end of content after skipping whitespace
            break

        try:
            # raw_decode attempts to decode a JSON object from the start of the string
            # and returns the decoded object and the index where it stopped parsing.
            obj, end_idx = decoder.raw_decode(full_content[idx:])
            parsed_entries.append(obj)
            idx += end_idx # Move index past the parsed object
        except json.JSONDecodeError as e:
            # If decoding fails, it means the current segment is not a valid JSON object.
            # We log a warning and advance the index by one to try parsing from the next character.
            # This is a heuristic to prevent infinite loops on malformed sections.
            print(f"⚠️ Skipping non-JSON or malformed content at index {idx}: {e} - Content snippet: '{full_content[idx:idx+50].strip()}...'")
            idx += 1
        except Exception as e:
            # Catch any other unexpected errors during raw_decode
            print(f"❌ An unexpected error occurred during parsing at index {idx}: {e} - Content snippet: '{full_content[idx:idx+50].strip()}...'")
            break # Break to prevent potential infinite loop on severe errors

    if not parsed_entries:
        print("No valid JSON objects were found or successfully parsed in the file.")
        # We don't exit here, as the file might still be created, just empty.
        # If no entries are found, the output file will be created but remain empty.

    # Open the output file for writing
    with open(output_file, "w", encoding="utf-8") as outfile:
        for entry_num, entry in enumerate(parsed_entries):
            # Extract the document URL and get the filename
            # Use .get() with a default value to prevent KeyError if 'document' is missing
            doc_name = extract_filename_from_url(entry.get("document", "Unknown Document"))

            # Write the document header to the output file
            outfile.write(f"\n📄 Document: {doc_name}\n" + "-"*80 + "\n")

            # Extract questions and answers, defaulting to empty lists if keys are missing
            questions = entry.get("questions", [])
            answers = entry.get("answers", [])

            # Iterate through questions and answers, pairing them up
            for i, (q, a) in enumerate(zip(questions, answers), 1):
                # Ensure q and a are strings before stripping, or handle potential non-string types
                q_str = str(q).strip() if not isinstance(q, str) else q.strip()
                a_str = str(a).strip() if not isinstance(a, str) else a.strip()
                # Write each question and answer pair to the output file
                outfile.write(f"Q{i}. {q_str}\nA{i}. {a_str}\n\n")

    print(f"✅ Output successfully saved to '{output_file}'")

except FileNotFoundError as e:
    print(f"❌ Error: {e}")
except Exception as e:
    print(f"❌ An unexpected error occurred: {e}")

