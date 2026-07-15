import random
import uuid
from datetime import datetime, timezone

from app.services import mongo_service
from app.models.game import (
    MIN_POOL_SIZE,
    MAX_POOL_SIZE,
    margin_for_round,
    modifier_fraction_for_round,
    modifier_magnitude_pct_for_round,
)

SECRET_MIN_ITEMS = 2
SECRET_MAX_ITEMS = 4
SECRET_MAX_QTY = 3


def _db():
    # Reuses mongo_service's connection helper (rather than opening a second
    # one) so the same test monkeypatch of mongo_service._get_db covers both.
    return mongo_service._get_db()


def _sessions_col():
    return _db()["game_sessions"]


def _rounds_col():
    return _db()["game_rounds"]


def _products_col():
    return _db()["products"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _build_round(player_name, session_id, round_number, pool_size):
    pool_size = max(MIN_POOL_SIZE, min(MAX_POOL_SIZE, pool_size))
    margin_pct = margin_for_round(round_number)

    all_products = list(_products_col().find())
    pool_size = min(pool_size, len(all_products))
    sampled = random.sample(all_products, pool_size) if pool_size else []

    fraction = modifier_fraction_for_round(round_number)
    magnitude_pct = modifier_magnitude_pct_for_round(round_number)
    num_modified = round(fraction * len(sampled))
    modified_indices = random.sample(range(len(sampled)), num_modified) if num_modified else []
    random.shuffle(modified_indices)
    half = len(modified_indices) // 2
    sale_indices = set(modified_indices[:half])
    increase_indices = set(modified_indices[half:])

    pool = []
    for i, p in enumerate(sampled):
        base_price = p["price"]
        if i in sale_indices:
            modifier = "sale"
            effective_price = round(base_price * (1 - magnitude_pct / 100), 2)
        elif i in increase_indices:
            modifier = "increase"
            effective_price = round(base_price * (1 + magnitude_pct / 100), 2)
        else:
            modifier = "normal"
            effective_price = base_price
        pool.append({
            "product_id": p["product_id"],
            "product_name": p["product_name"],
            "product_category": p.get("product_category"),
            "description": p.get("description", ""),
            "base_price": base_price,
            "price": effective_price,
            "modifier": modifier,
        })

    secret_count = min(len(pool), random.randint(SECRET_MIN_ITEMS, SECRET_MAX_ITEMS)) if pool else 0
    secret_items = random.sample(pool, secret_count) if secret_count else []
    secret = [
        {"product_id": item["product_id"], "quantity": random.randint(1, SECRET_MAX_QTY)}
        for item in secret_items
    ]

    price_by_id = {item["product_id"]: item["price"] for item in pool}
    target = round(sum(price_by_id[s["product_id"]] * s["quantity"] for s in secret), 2)

    doc = {
        "round_id": str(uuid.uuid4()),
        "session_id": session_id,
        "round_number": round_number,
        "margin_pct": margin_pct,
        "player_name": player_name,
        "pool": pool,
        "secret": secret,
        "target": target,
        "status": "active",
        "created_at": _now(),
    }
    _rounds_col().insert_one(doc)
    return doc


def create_session(player_name, pool_size):
    player_name = (player_name or "Anonymous").strip()[:40] or "Anonymous"
    session_id = str(uuid.uuid4())

    round_doc = _build_round(player_name, session_id, round_number=1, pool_size=pool_size)

    session_doc = {
        "session_id": session_id,
        "player_name": player_name,
        "status": "active",
        "round_number": 1,
        "margin_pct": round_doc["margin_pct"],
        "current_round_id": round_doc["round_id"],
        "rounds_survived": 0,
        "created_at": _now(),
    }
    _sessions_col().insert_one(session_doc)
    return session_doc, round_doc


def get_session(session_id):
    return _sessions_col().find_one({"session_id": session_id})


def get_round(round_id):
    return _rounds_col().find_one({"round_id": round_id})


def _score_round(round_doc, guesses):
    """Returns ((breakdown, total, difference), error_str)."""
    price_by_id = {item["product_id"]: item["price"] for item in round_doc["pool"]}
    unknown = [pid for pid in guesses if pid not in price_by_id]
    if unknown:
        return None, f"unknown product_id(s) in guesses: {', '.join(unknown)}"

    breakdown = []
    total = 0.0
    for item in round_doc["pool"]:
        pid = item["product_id"]
        qty = guesses.get(pid, 0)
        subtotal = round(item["price"] * qty, 2)
        total += subtotal
        breakdown.append({
            "product_id": pid,
            "product_name": item["product_name"],
            "price": item["price"],
            "modifier": item["modifier"],
            "quantity": qty,
            "subtotal": subtotal,
        })
    total = round(total, 2)
    difference = round(abs(total - round_doc["target"]), 2)
    return (breakdown, total, difference), None


def submit_session_guess(session_id, player_name, guesses):
    """Score a guess against the session's current round, then advance or
    end the session. Returns ({"round": ..., "session": ..., "next_round":
    ...}, error_str)."""
    session = _sessions_col().find_one({"session_id": session_id})
    if not session:
        return None, "session_not_found"
    if session["status"] != "active":
        return None, "session_already_ended"

    round_doc = _rounds_col().find_one({"round_id": session["current_round_id"]})
    if not round_doc or round_doc["status"] != "active":
        return None, "round_not_found"

    scored, err = _score_round(round_doc, guesses)
    if err:
        return None, err
    breakdown, total, difference = scored

    target = round_doc["target"]
    if target == 0:
        difference_pct = 0.0 if difference == 0 else 100.0
    else:
        difference_pct = round(difference / target * 100, 2)

    passed = difference_pct <= round_doc["margin_pct"]
    final_player_name = (player_name or round_doc["player_name"]).strip()[:40] or round_doc["player_name"]

    round_updates = {
        "status": "completed",
        "player_name": final_player_name,
        "guesses": guesses,
        "total_spent": total,
        "difference": difference,
        "difference_pct": difference_pct,
        "passed": passed,
        "completed_at": _now(),
    }
    _rounds_col().update_one({"round_id": round_doc["round_id"]}, {"$set": round_updates})
    round_doc.update(round_updates)
    round_doc["breakdown"] = breakdown

    session_updates = {"updated_at": _now(), "player_name": final_player_name}
    next_round_doc = None

    if passed:
        next_round_number = session["round_number"] + 1
        next_round_doc = _build_round(
            final_player_name, session_id, next_round_number, pool_size=len(round_doc["pool"])
        )
        session_updates.update({
            "round_number": next_round_number,
            "margin_pct": next_round_doc["margin_pct"],
            "current_round_id": next_round_doc["round_id"],
            "rounds_survived": session["round_number"],
        })
    else:
        session_updates.update({
            "status": "lost",
            "rounds_survived": session["round_number"] - 1,
            "lost_at": _now(),
        })

    _sessions_col().update_one({"session_id": session_id}, {"$set": session_updates})
    session.update(session_updates)

    return {"round": round_doc, "session": session, "next_round": next_round_doc}, None


def get_leaderboard(limit=10):
    limit = max(1, min(100, limit))
    docs = _sessions_col().find({"status": "lost"}).sort([("rounds_survived", -1), ("margin_pct", 1)]).limit(limit)
    return [
        {
            "session_id": d["session_id"],
            "player_name": d["player_name"],
            "rounds_survived": d["rounds_survived"],
            "margin_pct": d["margin_pct"],
            "lost_at": d.get("lost_at"),
        }
        for d in docs
    ]
