Note: will work only on windows

python -m venv venv

.\venv\Scripts\activate

pip install -r requirements.txt

uvicorn app:app --reload
