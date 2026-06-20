import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

BASE_DIR = Path(__file__).resolve().parent.parent

PROBLEMS_DIR = BASE_DIR / "problems"
LOGS_DIR = BASE_DIR / "logs"
SUBMISSIONS_DIR = BASE_DIR / "submissions"
FRONTEND_DIR = BASE_DIR / "frontend"

LOGS_DIR.mkdir(exist_ok=True)
SUBMISSIONS_DIR.mkdir(exist_ok=True)