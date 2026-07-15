from app.services import game_service
from app.models.game import margin_for_round, modifier_fraction_for_round, modifier_magnitude_pct_for_round


def _seed_products(client, prices):
    ids = []
    for i, price in enumerate(prices):
        resp = client.post("/products", json={
            "product_name": f"Item {i}",
            "product_category": "Misc",
            "price": price,
            "available_quantity": 100,
            "description": "",
        })
        ids.append(resp.get_json()["product_id"])
    return ids


def _make_deterministic(monkeypatch):
    """Pin game_service's randomness so pool order, secret combo, and
    quantities are reproducible: sample always takes the first k items in
    order, randint always returns the top of its range, shuffle is a no-op."""
    monkeypatch.setattr(game_service.random, "sample", lambda population, k: list(population)[:k])
    monkeypatch.setattr(game_service.random, "randint", lambda a, b: b)
    monkeypatch.setattr(game_service.random, "shuffle", lambda seq: None)


# --- pure schedule functions ---

def test_margin_shrinks_and_floors():
    assert margin_for_round(1) == 25.0
    assert margin_for_round(2) == 22.0
    assert margin_for_round(8) == 4.0  # floored
    assert margin_for_round(20) == 4.0


def test_modifiers_absent_round_one_and_ramp_after():
    assert modifier_fraction_for_round(1) == 0.0
    assert modifier_magnitude_pct_for_round(1) == 0.0
    assert modifier_fraction_for_round(2) > 0.0
    assert modifier_fraction_for_round(6) <= 0.6  # capped
    assert modifier_magnitude_pct_for_round(10) <= 35.0  # capped


# --- session routes ---

def test_start_session_round_one_has_no_modifiers_and_hides_prices(client):
    _seed_products(client, [10, 20, 30, 40, 50])

    resp = client.post("/game/sessions", json={"player_name": "Alice", "pool_size": 5})
    assert resp.status_code == 201
    body = resp.get_json()

    assert body["session"]["status"] == "active"
    assert body["session"]["round_number"] == 1
    assert body["session"]["margin_pct"] == 25.0
    assert body["round"]["margin_pct"] == 25.0
    assert "secret" not in body["round"]
    assert len(body["round"]["pool"]) == 5
    for item in body["round"]["pool"]:
        assert "price" not in item
        assert item["modifier"] == "normal"


def test_passing_a_round_advances_and_tightens_margin(client, monkeypatch):
    _seed_products(client, [10.0, 20.0, 30.0, 40.0])
    _make_deterministic(monkeypatch)

    start = client.post("/game/sessions", json={"player_name": "Bob", "pool_size": 10}).get_json()
    session_id = start["session"]["session_id"]
    guesses = {item["product_id"]: 3 for item in start["round"]["pool"]}

    resp = client.post(f"/game/sessions/{session_id}/guess", json={"guesses": guesses})
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["round"]["passed"] is True
    assert body["round"]["difference"] == 0
    assert body["session"]["status"] == "active"
    assert body["session"]["round_number"] == 2
    assert body["session"]["rounds_survived"] == 1
    assert body["session"]["margin_pct"] == margin_for_round(2)
    assert body["next_round"] is not None
    assert body["next_round"]["margin_pct"] == margin_for_round(2)
    # round 2 should start tagging sale/increase items
    assert any(item["modifier"] != "normal" for item in body["next_round"]["pool"])


def test_failing_a_round_ends_the_session(client, monkeypatch):
    _seed_products(client, [10.0, 20.0, 30.0, 40.0])
    _make_deterministic(monkeypatch)

    start = client.post("/game/sessions", json={"player_name": "Cara", "pool_size": 10}).get_json()
    session_id = start["session"]["session_id"]

    resp = client.post(f"/game/sessions/{session_id}/guess", json={"guesses": {}})
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["round"]["passed"] is False
    assert body["session"]["status"] == "lost"
    assert body["session"]["rounds_survived"] == 0
    assert body["next_round"] is None


def test_guess_on_ended_session_is_409(client, monkeypatch):
    _seed_products(client, [10.0, 20.0, 30.0, 40.0])
    _make_deterministic(monkeypatch)

    start = client.post("/game/sessions", json={"pool_size": 10}).get_json()
    session_id = start["session"]["session_id"]
    client.post(f"/game/sessions/{session_id}/guess", json={"guesses": {}})  # loses

    resp = client.post(f"/game/sessions/{session_id}/guess", json={"guesses": {}})
    assert resp.status_code == 409


def test_guess_on_missing_session_is_404(client):
    resp = client.post("/game/sessions/does-not-exist/guess", json={"guesses": {}})
    assert resp.status_code == 404


def test_guess_unknown_product_id_is_rejected(client):
    _seed_products(client, [10, 20, 30])
    start = client.post("/game/sessions", json={"pool_size": 3}).get_json()
    session_id = start["session"]["session_id"]

    resp = client.post(f"/game/sessions/{session_id}/guess", json={"guesses": {"does-not-exist": 1}})
    assert resp.status_code == 422


def test_get_session_hides_prices_while_active_and_reveals_after_loss(client, monkeypatch):
    _seed_products(client, [10.0, 20.0, 30.0, 40.0])
    _make_deterministic(monkeypatch)

    start = client.post("/game/sessions", json={"pool_size": 10}).get_json()
    session_id = start["session"]["session_id"]

    active = client.get(f"/game/sessions/{session_id}").get_json()
    for item in active["round"]["pool"]:
        assert "price" not in item

    client.post(f"/game/sessions/{session_id}/guess", json={"guesses": {}})  # loses

    after_loss = client.get(f"/game/sessions/{session_id}").get_json()
    assert after_loss["round"]["status"] == "completed"
    for item in after_loss["round"]["pool"]:
        assert "price" in item


def test_leaderboard_ranks_by_rounds_survived(client, monkeypatch):
    _seed_products(client, [10.0, 20.0, 30.0, 40.0])
    _make_deterministic(monkeypatch)

    # Session A: pass round 1, then deliberately miss round 2.
    a = client.post("/game/sessions", json={"player_name": "A", "pool_size": 10}).get_json()
    a_id = a["session"]["session_id"]
    a_guesses = {item["product_id"]: 3 for item in a["round"]["pool"]}
    client.post(f"/game/sessions/{a_id}/guess", json={"guesses": a_guesses})  # passes round 1
    client.post(f"/game/sessions/{a_id}/guess", json={"guesses": {}})  # fails round 2

    # Session B: miss round 1 immediately.
    b = client.post("/game/sessions", json={"player_name": "B", "pool_size": 10}).get_json()
    b_id = b["session"]["session_id"]
    client.post(f"/game/sessions/{b_id}/guess", json={"guesses": {}})

    resp = client.get("/game/leaderboard")
    assert resp.status_code == 200
    board = resp.get_json()

    a_entry = next(e for e in board if e["player_name"] == "A")
    b_entry = next(e for e in board if e["player_name"] == "B")
    assert a_entry["rounds_survived"] == 1
    assert b_entry["rounds_survived"] == 0
    assert board.index(a_entry) < board.index(b_entry)
