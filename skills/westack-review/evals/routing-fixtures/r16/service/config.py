import os

API_TOKEN = os.environ.get("API_TOKEN", "")
DEBUG = os.environ.get("DEBUG", "0") == "1"
