import pytest
from pymongo.errors import DuplicateKeyError

from app.services import mongo_service


def _create(app, **overrides):
    data = {
        "product_name": "Widget",
        "product_category": "Tools",
        "price": 9.99,
        "available_quantity": 10,
        "description": "",
    }
    data.update(overrides)
    with app.app_context():
        return mongo_service.create_product(data)


def test_get_products_by_ids_preserves_requested_order(app):
    _create(app, product_id="id-1", product_name="First")
    _create(app, product_id="id-2", product_name="Second")
    _create(app, product_id="id-3", product_name="Third")

    with app.app_context():
        # Deliberately out of insertion order, mimicking ES relevance ranking.
        result = mongo_service.get_products_by_ids(["id-3", "id-1", "id-2"])

    assert [p["product_id"] for p in result] == ["id-3", "id-1", "id-2"]


def test_get_products_by_ids_skips_missing_ids(app):
    _create(app, product_id="id-1")

    with app.app_context():
        result = mongo_service.get_products_by_ids(["id-1", "does-not-exist"])

    assert len(result) == 1
    assert result[0]["product_id"] == "id-1"


def test_get_products_by_ids_single_query_for_many_ids(app, monkeypatch):
    for i in range(5):
        _create(app, product_id=f"id-{i}")

    calls = []
    with app.app_context():
        col = mongo_service._col()
        real_find = col.find

        def spy_find(*args, **kwargs):
            calls.append((args, kwargs))
            return real_find(*args, **kwargs)

        monkeypatch.setattr(mongo_service, "_col", lambda: type("C", (), {"find": staticmethod(spy_find)})())
        mongo_service.get_products_by_ids([f"id-{i}" for i in range(5)])

    assert len(calls) == 1


def test_get_products_by_ids_empty_list_returns_empty(app):
    with app.app_context():
        assert mongo_service.get_products_by_ids([]) == []


def test_restore_product_reverts_fields_without_history(app):
    with app.app_context():
        mongo_service.create_product({
            "product_id": "id-1",
            "product_name": "Widget",
            "product_category": "Tools",
            "price": 9.99,
            "available_quantity": 10,
            "description": "",
        })
        snapshot = mongo_service.get_product("id-1")

        mongo_service.update_product("id-1", {"price": 5.0})
        assert mongo_service.get_product("id-1")["price"] == 5.0

        mongo_service.restore_product("id-1", snapshot)
        assert mongo_service.get_product("id-1")["price"] == 9.99

        # Restoring is not a tracked change.
        history_after_restore = mongo_service.get_product_history("id-1")
        assert len(history_after_restore) == 1  # only the original update_product call


def test_ensure_indexes_enforces_unique_product_id(app, fake_mongo_db):
    mongo_service.ensure_indexes(fake_mongo_db)

    with app.app_context():
        mongo_service.create_product({
            "product_id": "dup-id",
            "product_name": "First",
            "product_category": "Tools",
            "price": 9.99,
            "available_quantity": 10,
        })
        with pytest.raises(DuplicateKeyError):
            fake_mongo_db["products"].insert_one({
                "product_id": "dup-id",
                "product_name": "Second",
                "product_category": "Tools",
                "price": 5.0,
                "available_quantity": 1,
            })


def test_create_product_sets_created_and_updated_at(app):
    with app.app_context():
        product = mongo_service.create_product({
            "product_id": "id-ts",
            "product_name": "Widget",
            "product_category": "Tools",
            "price": 9.99,
            "available_quantity": 10,
        })
        assert product["created_at"] == product["updated_at"]

        updated = mongo_service.update_product("id-ts", {"price": 5.0})
        assert updated["updated_at"] >= updated["created_at"]
        assert updated["created_at"] == product["created_at"]  # unchanged by the update
