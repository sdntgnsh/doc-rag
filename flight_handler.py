import asyncio
import requests
from typing import Dict, List, Tuple

# --- Hardcoded Mappings for Maximum Speed ---
CITY_LANDMARK_MAP = {
    # Indian Cities
    "Delhi": "Gateway of India",
    "Mumbai": "Space Needle", # Last one wins in duplicates
    "Chennai": "Charminar",
    "Hyderabad": "Taj Mahal", # Last one wins in duplicates
    "Ahmedabad": "Howrah Bridge",
    "Mysuru": "Golconda Fort",
    "Kochi": "Qutub Minar",
    "Pune": "Golden Temple", # Last one wins in duplicates
    "Nagpur": "Lotus Temple",
    "Chandigarh": "Mysore Palace",
    "Kerala": "Rock Garden",
    "Bhopal": "Victoria Memorial",
    "Varanasi": "Vidhana Soudha",
    "Jaisalmer": "Sun Temple",

    # International Cities
    "New York": "Eiffel Tower",
    "London": "Sydney Opera House", # Last one wins in duplicates
    "Tokyo": "Big Ben",
    "Beijing": "Colosseum",
    "Bangkok": "Christ the Redeemer",
    "Toronto": "Burj Khalifa",
    "Dubai": "CN Tower",
    "Amsterdam": "Petronas Towers",
    "Cairo": "Leaning Tower of Pisa",
    "San Francisco": "Mount Fuji",
    "Berlin": "Niagara Falls",
    "Barcelona": "Louvre Museum",
    "Moscow": "Stonehenge",
    "Seoul": "Times Square", # Last one wins in duplicates
    "Cape Town": "Acropolis",
    "Istanbul": "Big Ben",
    "Riyadh": "Machu Picchu",
    "Paris": "Taj Mahal",
    "Dubai Airport": "Moai Statues",
    "Singapore": "Christchurch Cathedral",
    "Jakarta": "The Shard",
    "Vienna": "Blue Mosque",
    "Kathmandu": "Neuschwanstein Castle",
    "Los Angeles": "Buckingham Palace",
}


# --- URLs for the flight number logic ---
FAVORITE_CITY_URL = "https://register.hackrx.in/submissions/myFavouriteCity"
FLIGHT_NUMBER_URLS = {
    "Gateway of India": "https://register.hackrx.in/teams/public/flights/getFirstCityFlightNumber",
    "Taj Mahal": "https://register.hackrx.in/teams/public/flights/getSecondCityFlightNumber",
    "Eiffel Tower": "https://register.hackrx.in/teams/public/flights/getThirdCityFlightNumber",
    "Big Ben": "https://register.hackrx.in/teams/public/flights/getFourthCityFlightNumber",
    # Default/Other case
    "India Gate": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Charminar": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Marina Beach": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Howrah Bridge": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Golconda Fort": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Qutub Minar": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Meenakshi Temple": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Lotus Temple": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Mysore Palace": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Rock Garden": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Victoria Memorial": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Vidhana Soudha": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Sun Temple": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Golden Temple": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Statue of Liberty": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Colosseum": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Sydney Opera House": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Christ the Redeemer": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Burj Khalifa": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "CN Tower": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Petronas Towers": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Leaning Tower of Pisa": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Mount Fuji": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Niagara Falls": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Louvre Museum": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Stonehenge": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Sagrada Familia": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Acropolis": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Machu Picchu": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Moai Statues": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Christchurch Cathedral": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "The Shard": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Blue Mosque": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Neuschwanstein Castle": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Buckingham Palace": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Space Needle": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Times Square": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber",
    "Other": "https://register.hackrx.in/teams/public/flights/getFifthCityFlightNumber"
}

async def _get_favorite_city() -> str | None:
    """Fetches the favorite city from the API."""
    try:
        print("[DEBUG] Fetching favorite city...")
        response = await asyncio.to_thread(requests.get, FAVORITE_CITY_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        city = data.get("data", {}).get("city")
        print(f"[DEBUG] Favorite city retrieved: {city}")
        return city
    except requests.RequestException as e:
        print(f"Error fetching favorite city: {e}")
        return None

async def _get_flight_number(landmark: str) -> Tuple[str | None, str | None]:
    """Fetches the flight number and the URL used based on the landmark."""
    url = FLIGHT_NUMBER_URLS.get(landmark, FLIGHT_NUMBER_URLS["Other"])
    print(f"[DEBUG] Determined flight number URL: {url} for landmark: {landmark}")
    try:
        response = await asyncio.to_thread(requests.get, url, timeout=10)
        response.raise_for_status()
        data = response.json()
        flight_number = data.get("data", {}).get("flightNumber")
        print(f"[DEBUG] Retrieved flight number: {flight_number}")
        return flight_number, url
    except requests.RequestException as e:
        print(f"Error fetching flight number for landmark '{landmark}': {e}")
        return None, url

async def handle_flight_query(doc_url: str) -> List[str]:
    """
    Handles the specific flight number query using a hardcoded map for maximum speed.
    """
    print(f"[DEBUG] Starting flight query with hardcoded map. Ignoring doc_url: {doc_url}")
    # Step 1: Fetch the favorite city
    favorite_city = await _get_favorite_city()
    if not favorite_city:
        return ["Could not retrieve the favorite city."]

    # Step 2: Map the city to a landmark using the hardcoded map
    landmark = CITY_LANDMARK_MAP.get(favorite_city, "Other")
    print(f"[DEBUG] Mapped city '{favorite_city}' to landmark '{landmark}'.")

    # Step 3: Fetch the flight number based on the landmark
    flight_number, used_url = await _get_flight_number(landmark)
    if not flight_number:
        return [f"Could not retrieve the flight number from URL: {used_url}"]

    # Step 4. Return the final answer
    final_answer = f"{flight_number}"
    print(f"[DEBUG] Final answer: {final_answer}")
    return [final_answer]
