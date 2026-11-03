import pytest
from fastapi.testclient import TestClient

from supportforge.agent import SupportAgent
from supportforge.app import create_app
from supportforge.config import Settings
from supportforge.knowledge import KnowledgeBase
from supportforge.store import Store


@pytest.fixture
def settings(tmp_path):
    return Settings(database=tmp_path / "test.sqlite3")


@pytest.fixture
def store(settings):
    database = Store(settings.database)
    database.initialize()
    return database


@pytest.fixture
def knowledge(store, settings):
    base = KnowledgeBase(store)
    base.ingest(settings.knowledge_dir)
    return base


@pytest.fixture
def agent(settings, store, knowledge):
    return SupportAgent(settings, store, knowledge)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as connection:
        yield connection
