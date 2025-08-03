import json
import os
import requests
from urllib.parse import urlparse, unquote

def download_pdfs_from_json(json_file_path, output_folder):
    """
    Reads a JSON file containing document URLs, downloads each PDF,
    and saves them to a specified output folder.

    Args:
        json_file_path (str): The path to the input JSON file.
        output_folder (str): The name of the folder to save PDFs into.
    """
    # Create the output folder if it doesn't already exist
    os.makedirs(output_folder, exist_ok=True)
    print(f"✅ Output folder '{output_folder}' is ready.")

    # Read the JSON file
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: The file '{json_file_path}' was not found.")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: Could not decode JSON from the file '{json_file_path}'.")
        return

    # A set to keep track of downloaded URLs to avoid duplicates
    downloaded_urls = set()

    # Loop through each record in the JSON data
    for i, record in enumerate(data):
        if 'documents' not in record:
            print(f"⚠️ Skipping record {i+1} as it has no 'documents' key.")
            continue

        url = record['documents']

        # Skip if this URL has already been processed
        if url in downloaded_urls:
            print(f"ℹ️ Skipping duplicate URL: {url}")
            continue

        try:
            # Extract a clean filename from the URL
            # 1. Parse the URL to isolate the path component
            #    e.g., /assets/Super_Splendor_(Feb_2023).pdf
            path = urlparse(url).path
            
            # 2. Get the basename of the path
            #    e.g., Super_Splendor_(Feb_2023).pdf
            filename_encoded = os.path.basename(path)
            
            # 3. Decode URL-encoded characters like '%20' into spaces
            filename = unquote(filename_encoded)

            save_path = os.path.join(output_folder, filename)

            print(f"\n⬇️  Downloading '{filename}'...")

            # Perform the download request
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

            # Save the file in chunks
            with open(save_path, 'wb') as pdf_file:
                for chunk in response.iter_content(chunk_size=8192):
                    pdf_file.write(chunk)

            print(f"👍 Successfully saved to '{save_path}'")
            downloaded_urls.add(url)

        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading {url}: {e}")
        except Exception as e:
            print(f"❌ An unexpected error occurred for URL {url}: {e}")

if __name__ == "__main__":
    # Configuration
    INPUT_JSON_FILE = "query.json"
    OUTPUT_PDF_FOLDER = "pdf"

    # Execute the function
    download_pdfs_from_json(INPUT_JSON_FILE, OUTPUT_PDF_FOLDER)