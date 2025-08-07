from utils import clean_text, get_text_from_url




print(get_text_from_url("https://register.hackrx.in/utils/get-secret-token?hackTeam=4366"))


def extract_secret_token(input_string, question=None):
    """
    Extracts a secret token from a specific string format.

    This function is designed to find and return the token from a string
    that follows the pattern: "... Your Secret Token [TOKEN]".

    Args:
        input_string (str): The string containing the token.

    Returns:
        str: The extracted secret token.
        None: If the token pattern is not found in the string.
    """
    try:
        # Define the unique text that comes just before the token.
        delimiter = "Your Secret Token "

        

        # Split the string by the delimiter. The token will be the second element.
        # For example: "part1<delimiter>part2".split(delimiter) -> ['part1', 'part2']
        parts = input_string.split(delimiter)

        # Check if the split was successful (i.e., the delimiter was found)
        if len(parts) > 1:
            # The token is the second part. Use .strip() to remove any
            # leading/trailing whitespace.
            token = parts[1].strip()
            return token
        else:
            # The delimiter was not found in the string.
            return input_string

    except Exception as e:
        # Handle any unexpected errors during the process.
        print(f"An error occurred while extracting the token: {e}")
        return input_string



async def answer_from_website(doc_url):
    """
    Fetches and processes text from a given URL, returning answers to questions.

    This function retrieves the content from the specified URL, cleans it,
    and generates answers based on the provided questions.

    Args:
        doc_url (str): The URL of the website to scrape.

    Returns:
        list: A list of cleaned answers extracted from the webpage.
    """
    # Fetch and clean text from the URL
    text_content = get_text_from_url(doc_url)


    if "Secret Token 🔒 Your Secret Token" not in text_content:
            return[text_content]

    print(text_content)

    final_token = extract_secret_token(text_content)
    
    if not final_token:

        if not text_content:
            return ["No content found at the provided URL."]
        

        return [text_content]


    return [final_token]  