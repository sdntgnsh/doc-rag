Note: will work only on windows

python -m venv venv

.\venv\Scripts\activate

pip install -r requirements.txt

uvicorn app:app --reload 
then wait till startup and send queries to localhost:8000

