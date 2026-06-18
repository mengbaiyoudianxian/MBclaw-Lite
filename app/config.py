import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'mbclaw.db')}"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "")
CHROMA_PATH = os.path.join(DATA_DIR, "chroma")
