import os
import shutil
import pytest
from fastapi.testclient import TestClient
from app.database import init_db, SessionLocal, engine, Base
from app.main import app
from app.config import DATA_DIR


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Clean filesystem memory/transcript dirs (NOT chroma - ChromaDB holds file locks)
    for sub in ("memory", "transcripts"):
        path = os.path.join(DATA_DIR, sub)
        if os.path.exists(path):
            shutil.rmtree(path)
    # Reset ChromaDB collection cache
    from app.services.vector_store import _collections
    _collections.clear()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
