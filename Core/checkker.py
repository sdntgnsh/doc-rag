import os
import pickle

def search_query_in_cache(query, cache_dir='./cache'):
    results = []
    for filename in os.listdir(cache_dir):
        if filename.endswith('.pkl'):
            filepath = os.path.join(cache_dir, filename)
            with open(filepath, 'rb') as f:
                try:
                    data = pickle.load(f)
                except Exception as e:
                    print(f"Could not load {filename}: {e}")
                    continue

                # Search logic for common types
                if isinstance(data, dict):
                    for k, v in data.items():
                        if query.lower() in str(k).lower() or query.lower() in str(v).lower():
                            results.append((filename, k, v))
                elif isinstance(data, list):
                    for item in data:
                        if query.lower() in str(item).lower():
                            results.append((filename, item))
                else:
                    if query.lower() in str(data).lower():
                        results.append((filename, data))
    return results

# Example usage:
query = "heart surgery."
matches = search_query_in_cache(query)
for match in matches:
    print(match)