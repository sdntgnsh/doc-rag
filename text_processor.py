# text_processor.py
from typing import List
import numpy as np
import nltk
from sklearn.metrics.pairwise import cosine_similarity
import os
import openai
from dotenv import load_dotenv

# --- Load Environment Variables and Configure OpenAI ---
# It's good practice to load environment variables at the top of the script.
load_dotenv()
# Make sure your OPENAI_API_KEY is set in your .env file or environment
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- NLTK Setup ---
# Define a local path for NLTK data to avoid permission issues in environments like WSL.
LOCAL_NLTK_DATA_PATH = os.path.join(os.getcwd(), 'nltk_data')

# Add the local path to NLTK's data search path.
if LOCAL_NLTK_DATA_PATH not in nltk.data.path:
    nltk.data.path.append(LOCAL_NLTK_DATA_PATH)

# Ensure all required NLTK tokenizer data is downloaded to the local path.
# The 'punkt_tab' resource is sometimes required in addition to 'punkt'.
required_nltk_resources = ['punkt', 'punkt_tab']
for resource in required_nltk_resources:
    print(f"NLTK '{resource}' resource not found. Downloading to {LOCAL_NLTK_DATA_PATH}...")
    # The download will be attempted to the specified local data path.
    nltk.download(resource, quiet=True, download_dir=LOCAL_NLTK_DATA_PATH)
    print(f"Download of '{resource}' complete.")


# --- Constants ---
EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100  # Safe batch size for the OpenAI API

# --- Embedding Function ---
def get_openai_embeddings(texts: List[str]) -> np.ndarray:
    """
    Generates embeddings for a list of texts using OpenAI's API.

    This function takes a list of text strings, cleans them by removing any
    empty or non-string entries, and then sends them to the OpenAI Embeddings API
    in batches to generate vector embeddings. It includes error handling for API calls.

    Args:
        texts: A list of text strings to embed.

    Returns:
        A numpy array of shape (n_texts, embedding_dimension), where each row
        is the embedding vector for the corresponding text. Returns an empty
        array if the input is empty or after cleaning results in no valid texts.
    """
    # 1. Filter out any empty or non-string inputs to avoid API errors.
    valid_texts = [t for t in texts if isinstance(t, str) and t.strip()]
    if not valid_texts:
        return np.array([])

    all_embeddings = []
    
    # 2. Process the texts in batches to stay within API limits.
    for i in range(0, len(valid_texts), BATCH_SIZE):
        batch = valid_texts[i:i + BATCH_SIZE]
        try:
            # 3. Call the OpenAI API to get embeddings for the batch.
            response = openai.embeddings.create(
                model=EMBED_MODEL,
                input=batch
            )
            # 4. Extract the embedding vectors from the API response.
            batch_embeddings = [record.embedding for record in response.data]
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            # 5. Handle potential errors during the API call.
            print(f"❌ OpenAI API call failed for a batch: {e}")
            # As a fallback, add zero vectors for the failed batch to ensure
            # the length of the output matches the number of input sentences.
            # The embedding dimension for text-embedding-3-small is 1536.
            embedding_dimension = 1536
            all_embeddings.extend([[0.0] * embedding_dimension] * len(batch))

    return np.array(all_embeddings)


# --- Semantic Chunking Function ---
def chunk_text(
    semantic_chunks: List[str],
    similarity_percentile_threshold: float = 95.0
) -> List[str]:
    """
    Chunks text semantically based on the cosine similarity of sentence embeddings.

    This function processes a list of pre-segmented chunks (like paragraphs or tables).
    - Markdown tables are kept as whole, indivisible chunks.
    - For text paragraphs, it performs the following steps:
        1. Splits the paragraph into individual sentences.
        2. Generates an embedding for each sentence using the provided function.
        3. Calculates the cosine similarity between adjacent sentences.
        4. Identifies split points where the similarity drops significantly. A drop is
           defined as being in the lower part of the similarity distribution, controlled
           by the `similarity_percentile_threshold`.
        5. Groups sentences into semantically coherent chunks.

    Args:
        semantic_chunks: A list of strings, where each string is a paragraph or a Markdown table.
        similarity_percentile_threshold: The percentile for similarity scores that will be used
            as the cutoff for creating a new chunk. A higher value (e.g., 95) means fewer,
            larger chunks, as splits only happen at very noticeable topic shifts. A lower value
            (e.g., 80) results in more, smaller chunks.

    Returns:
        A list of semantically coherent text chunks.
    """
    final_chunks = []

    for chunk in semantic_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        # Keep Markdown tables as single, unsplittable units.
        if chunk.startswith('|') and chunk.endswith('|'):
            final_chunks.append(chunk)
            continue

        # 1. Split the paragraph into sentences.
        # The 'punkt' data is now checked and downloaded at the module level.
        sentences = nltk.sent_tokenize(chunk)
        
        # If there's only one sentence or less, no need for semantic splitting.
        if len(sentences) <= 1:
            final_chunks.append(chunk)
            continue

        # 2. Generate embeddings for each sentence.
        embeddings = get_openai_embeddings(sentences)
        
        # If embedding generation failed or returned nothing, skip this chunk.
        if embeddings.shape[0] == 0:
            continue

        # 3. Calculate cosine similarity between adjacent sentences.
        similarities = []
        for i in range(len(embeddings) - 1):
            embedding_current = embeddings[i].reshape(1, -1)
            embedding_next = embeddings[i+1].reshape(1, -1)
            sim = cosine_similarity(embedding_current, embedding_next)[0][0]
            similarities.append(sim)

        # If there are no similarities, it means there was only one sentence after processing.
        if not similarities:
            final_chunks.append(" ".join(sentences))
            continue
            
        # 4. Identify split points based on the similarity threshold.
        threshold = np.percentile(similarities, 100 - similarity_percentile_threshold)

        # 5. Group sentences into new chunks.
        current_chunk_sentences = [sentences[0]]
        for i, sim in enumerate(similarities):
            if sim < threshold:
                final_chunks.append(" ".join(current_chunk_sentences))
                current_chunk_sentences = [sentences[i+1]]
            else:
                current_chunk_sentences.append(sentences[i+1])

        # Add the last remaining chunk to the list.
        if current_chunk_sentences:
            final_chunks.append(" ".join(current_chunk_sentences))

    # Filter out any potential empty strings that might have been added.
    return [c for c in final_chunks if c]
