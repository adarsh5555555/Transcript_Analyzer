from pathlib import Path

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
CACHE_DIR = Path(os.getenv("CACHE_DIR", ROOT / ".cache"))    # writable; /tmp on serverless
SEED_CACHE_DIR = ROOT / ".cache"    # read-only analyses shipped with the repo (the sample run)
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Bump when parsing, prompts or verification change, so cached analyses are recomputed.
PIPELINE_VERSION = "3"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
SAMPLE_TRANSCRIPTS = ["Transcript_1_Netherlands.txt", "Transcript_2_Poland.txt", "Transcript_3_Spain.txt"]
SAMPLE_GUIDE = "Interview_Guide.txt"

# Postgres when set (Neon/Supabase work well); JSON files when empty.
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Public deploys: set APP_PASSCODE to gate the API, since analyses cost API credits.
APP_PASSCODE = os.getenv("APP_PASSCODE", "")
ANALYSES_PER_HOUR = int(os.getenv("ANALYSES_PER_HOUR", "12"))
QUESTIONS_PER_HOUR = int(os.getenv("QUESTIONS_PER_HOUR", "80"))

MAX_FILES = 50
MAX_FILE_BYTES = 1_000_000
