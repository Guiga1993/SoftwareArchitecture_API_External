import os

from dotenv import load_dotenv

load_dotenv()

SHIPPO_API_KEY = os.getenv("SHIPPO_API_KEY")

SHIPPO_BASE_URL = "https://api.goshippo.com"