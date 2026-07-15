import fakeredis
import mongomock
import pytest

from app.main import create_app
from app.services import cache_service, es_service, mongo_service
from tests.fakes import FakeElasticsearch


@pytest.fixture
def fake_mongo_db():
    return mongomock.MongoClient().get_database("inventory")


@pytest.fixture
def fake_redis():
    return fakeredis.FakeStrictRedis()


@pytest.fixture
def fake_es():
    return FakeElasticsearch()


@pytest.fixture
def app(monkeypatch, fake_mongo_db, fake_redis, fake_es):
    """Flask app wired to in-memory fakes instead of real Mongo/Redis/ES."""
    monkeypatch.setattr(mongo_service, "_get_db", lambda: fake_mongo_db)
    monkeypatch.setattr(cache_service, "_get_client", lambda: fake_redis)
    monkeypatch.setattr(es_service, "_get_client", lambda: fake_es)

    flask_app = create_app()
    # Rate limiting and API-key auth are exercised in isolation in
    # tests/test_security.py; disabling both here keeps the ~60 CRUD tests
    # in the rest of the suite from tripping the write-endpoint rate limit
    # when run back-to-back against the same shared Limiter instance.
    flask_app.config.update(TESTING=True, RATELIMIT_ENABLED=False, API_KEY=None)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_product():
    return {
        "product_name": "Mechanical Keyboard",
        "product_category": "Electronics",
        "price": 149.99,
        "available_quantity": 30,
        "description": "TKL mechanical keyboard with Cherry MX switches.",
    }
