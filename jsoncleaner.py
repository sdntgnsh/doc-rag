import json
import argparse # Used for parsing command-line arguments

def format_qa_from_json(input_json_file, output_txt_file):
    """
    Reads a JSON file containing a list of Q&A records, formats them,
    and saves the result to a text file.
    """
    # --- 1. Read and parse the specified JSON file ---
    try:
        with open(input_json_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Input file not found at '{input_json_file}'")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: Failed to decode JSON from '{input_json_file}'. Please check the file's format.")
        return

    all_formatted_content = []

    # --- 2. Iterate through each record in the JSON list ---
    for record in records:
        pdf_url = record.get("document", "URL not provided")
        questions = record.get("questions", [])
        answers = record.get("answers", [])
        
        # Start formatting the output for this record
        record_content = []
        record_content.append(f"PDF URL: {pdf_url}")
        record_content.append("----------------------------------------\n")

        # --- 3. Pair questions and answers ---
        for i, (question, answer) in enumerate(zip(questions, answers)):
            record_content.append(f"Question: {question}")
            record_content.append(f"Answer: {answer}\n")
        
        all_formatted_content.append("\n".join(record_content))

    # --- 4. Write the formatted content to the output file ---
    try:
        with open(output_txt_file, 'w', encoding='utf-8') as f:
            # Join all formatted records with a clear separator
            f.write("========================================\n\n".join(all_formatted_content))
        print(f"✅ Success! Data from '{input_json_file}' has been saved to '{output_txt_file}'")
    except IOError as e:
        print(f"❌ Error: Could not write to file '{output_txt_file}'. Reason: {e}")


if __name__ == "__main__":
    # --- Set up command-line argument parsing ---
    parser = argparse.ArgumentParser(
        description="A script to format Q&A data from a specified JSON file into a readable text file."
    )
    


    # --- Call the main function with the provided file paths ---
    format_qa_from_json(input_json_file="submission2.json", output_txt_file="cleaned_file.txt")