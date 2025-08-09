import json
import requests
from typing import List
import time
import threading

class QueryExpander:
    def __init__(self):
        self.model_name = "phi"
        self.ollama_url = "http://localhost:11434/api/generate"
        self.cache = {}
        self.cache_lock = threading.Lock()
        self.generation_config = {
            "temperature": 0.6,
            "top_p": 0.8,
            "num_predict": 80,
            "num_ctx": 1024,
        }
        self._warmup()

    def _warmup(self):
        try:
            self._generate("Test")
        except:
            pass

    def expand(self, query: str) -> List[str]:
        with self.cache_lock:
            if query in self.cache:
                return self.cache[query]

        prompt = f'Rewrite "{query}" in 3 different ways for search. Return JSON array: ["way1", "way2", "way3"]'
        try:
            response = self._generate(prompt)
            variations = self._parse_json(response)
            if variations:
                result = [query] + variations
                with self.cache_lock:
                    self.cache[query] = result
                return result
        except:
            pass

        return [query]

    def _generate(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": self.generation_config
        }

        response = requests.post(self.ollama_url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get("response", "")
        raise Exception(f"Ollama error: {response.status_code}")

    def _parse_json(self, text: str) -> List[str]:
        try:
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end > start:
                json_str = text[start:end]
                result = json.loads(json_str)
                if isinstance(result, list):
                    return [str(item) for item in result[:3]]
        except:
            pass
        return []

    def get_cache_stats(self):
        with self.cache_lock:
            return {query: len(variations) for query, variations in self.cache.items()}

if __name__ == "__main__":
    expander = QueryExpander()
    test_query = "What are renewable energy sources?"
    result = expander.expand(test_query)
    print(f"Expanded: {result}")
    result2 = expander.expand(test_query)
    print(f"Cache result: {result2}")
    print(f"Cache stats: {expander.get_cache_stats()}")
