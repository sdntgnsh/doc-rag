Note: for ppt files will work only on windows with power point installed(we will add better handling later)

make .env file in root and fill with your api based on .env.example
python -m venv venv

.\venv\Scripts\activate

pip install -r requirements.txt

uvicorn app:app --reload

then wait till startup and send queries to localhost:8000
