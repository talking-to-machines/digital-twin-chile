import os
from dotenv import load_dotenv


load_dotenv(dotenv_path="config/.env")

X_API_USERNAME = os.getenv("X_API_USERNAME")
X_API_PASSWORD = os.getenv("X_API_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = "gpt-5-mini-2025-08-07"  # gpt-4.1-2025-04-14, gpt-5-mini-2025-08-07
TOP_N_PROFILES = 100
WAIT_TIME_BETWEEN_RETRIEVAL_REQUESTS = 300  # in seconds
MAX_RETRIES = 5
