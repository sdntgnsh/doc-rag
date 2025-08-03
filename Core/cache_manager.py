import os
import pickle
from typing import Any, Tuple

# Place cache directory in parent directory
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pdf_cache")

def _get_cache_filepath(key: Tuple[int, str]) -> str:
    """Creates a safe filename from the cache key."""
    page_count, first_word = key
    # Sanitize the first word to be a valid filename component
    safe_word = "".join(c for c in first_word if c.isalnum())
    filename = f"{page_count}_{safe_word}.pkl"
    return os.path.join(CACHE_DIR, filename)

def save_to_cache(key: Tuple[int, str], obj: Any):
    """Serializes and saves an object to a file on disk."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    
    filepath = _get_cache_filepath(key)
    try:
        with open(filepath, 'wb') as f:
            pickle.dump(obj, f)
        print(f"Saved object to disk cache: {filepath}")
    except Exception as e:
        print(f"Error saving to cache file {filepath}: {e}")

def load_from_cache(key: Tuple[int, str]) -> Any | None:
    """Loads and deserializes an object from a file on disk if it exists."""
    filepath = _get_cache_filepath(key)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'rb') as f:
                print(f"Loading object from disk cache: {filepath}")
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading from cache file {filepath}: {e}")
            return None
    return None