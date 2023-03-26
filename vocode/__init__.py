import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("VOCODE_API_KEY")
base_url = os.getenv("VOCODE_BASE_URL", "vocode-api-5xerktxr4q-uc.a.run.app")
