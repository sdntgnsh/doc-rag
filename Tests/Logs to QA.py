import json  # Use json for parsing JSON data
import os    # For checking file existence

# Define input and output file paths
# IMPORTANT: Replace 'your_input_file.jsonl' with the actual path to your JSONL file.
# For example: input_file = r"C:\Users\YourUser\Documents\my_logs.jsonl"
input_file = "logs.jsonl"  # <--- **CHANGE THIS TO YOUR ACTUAL INPUT FILE PATH**
output_file = os.path.join("Text Files", "Round 2 Submission 2.txt")
# Ensure the output directory exists
os.makedirs(os.path.dirname(output_file), exist_ok=True)

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
        if idx >= len(full_content):  # Reached end of content after skipping whitespace
            break

        try:
            # raw_decode attempts to decode a JSON object from the start of the string
            obj, end_idx = decoder.raw_decode(full_content[idx:])
            parsed_entries.append(obj)
            idx += end_idx  # Move index past the parsed object
        except json.JSONDecodeError as e:
            # If decoding fails, skip the malformed section
            print(f"⚠️ Skipping non-JSON or malformed content at index {idx}: {e} - Content snippet: '{full_content[idx:idx+50].strip()}...'")
            idx += 1
        except Exception as e:
            # Catch any other unexpected errors
            print(f"❌ An unexpected error occurred during parsing at index {idx}: {e} - Content snippet: '{full_content[idx:idx+50].strip()}...'")
            break

    if not parsed_entries:
        print("No valid JSON objects were found or successfully parsed in the file.")
        # If no entries are found, the output file will be created but remain empty.

    # Open the output file for writing
    with open(output_file, "w", encoding="utf-8") as outfile:
        for entry_num, entry in enumerate(parsed_entries):
            # Use the full document URL directly from the JSON entry
            # Use .get() with a default value to prevent KeyError
            doc_url = entry.get("document", "Unknown Document URL")

            # Write the document header with the full URL to the output file
            outfile.write(f"\n📄 Document URL: {doc_url}\n" + "-" * 80 + "\n")

            # Extract questions and answers, defaulting to empty lists if keys are missing
            questions = entry.get("questions", [])
            answers = entry.get("answers", [])

            # Iterate through questions and answers, pairing them up
            for i, (q, a) in enumerate(zip(questions, answers), 1):
                # Ensure q and a are strings before processing
                q_str = str(q).strip()
                a_str = str(a).strip()
                # Write each question and answer pair to the output file
                outfile.write(f"Q{i}. {q_str}\nA{i}. {a_str}\n\n")

    print(f"✅ Output successfully saved to '{output_file}'")

except FileNotFoundError as e:
    print(f"❌ Error: {e}")
except Exception as e:
    print(f"❌ An unexpected error occurred: {e}")