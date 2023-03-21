import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("VOCODE_API_KEY")
base_url = os.getenv("VOCODE_BASE_URL", "api.vocode.dev")
