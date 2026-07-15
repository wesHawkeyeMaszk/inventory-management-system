MIN_POOL_SIZE = 4
MAX_POOL_SIZE = 25
DEFAULT_POOL_SIZE = 10

# Each round's margin (max allowed % difference between spend and target to
# pass) shrinks as the session goes on, floored so late rounds stay winnable
# but demand near-perfect play.
START_MARGIN_PCT = 25.0
MARGIN_STEP_PCT = 3.0
MIN_MARGIN_PCT = 4.0

# Sale/price-increase tags ramp in starting the second round so round 1
# teaches the base game, then grow in coverage and intensity each round.
MODIFIER_START_ROUND = 2
MODIFIER_MAX_FRACTION = 0.6
MODIFIER_FRACTION_STEP = 0.15
MODIFIER_BASE_MAGNITUDE_PCT = 10.0
MODIFIER_MAGNITUDE_STEP_PCT = 5.0
MODIFIER_MAX_MAGNITUDE_PCT = 35.0


def margin_for_round(round_number):
    margin = START_MARGIN_PCT - (round_number - 1) * MARGIN_STEP_PCT
    return round(max(MIN_MARGIN_PCT, margin), 2)


def modifier_fraction_for_round(round_number):
    """Share of the pool tagged sale/increase this round (0 before MODIFIER_START_ROUND)."""
    if round_number < MODIFIER_START_ROUND:
        return 0.0
    steps = round_number - MODIFIER_START_ROUND + 1
    return min(MODIFIER_MAX_FRACTION, MODIFIER_FRACTION_STEP * steps)


def modifier_magnitude_pct_for_round(round_number):
    """How far a sale/increase multiplier swings off the base price this round."""
    if round_number < MODIFIER_START_ROUND:
        return 0.0
    steps = round_number - MODIFIER_START_ROUND
    magnitude = MODIFIER_BASE_MAGNITUDE_PCT + MODIFIER_MAGNITUDE_STEP_PCT * steps
    return min(MODIFIER_MAX_MAGNITUDE_PCT, magnitude)


def validate_guess(data):
    """Validate a submitted guess payload. Returns (cleaned_data, error_str).

    Expected shape: {"player_name": str, "guesses": {product_id: quantity}}
    """
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object"

    guesses = data.get("guesses")
    if not isinstance(guesses, dict):
        return None, "guesses must be an object mapping product_id to quantity"

    cleaned_guesses = {}
    for product_id, quantity in guesses.items():
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            return None, f"quantity for {product_id} must be an integer"
        if quantity < 0:
            return None, f"quantity for {product_id} must be non-negative"
        if quantity > 0:
            cleaned_guesses[product_id] = quantity

    # None (rather than a default) when omitted, so callers that persist
    # this onto an existing round/session don't clobber the player's
    # already-known name with "Anonymous" on every subsequent guess.
    raw_name = data.get("player_name")
    player_name = str(raw_name).strip()[:40] or None if raw_name else None

    return {"player_name": player_name, "guesses": cleaned_guesses}, None


def serialize_round(doc, reveal=False):
    """Convert a game round Mongo document to a JSON-serialisable dict.

    When reveal is False (round still active), item prices are stripped so
    the client can't read them out of the response. The sale/increase
    "modifier" tag stays visible either way - it's a deliberate hint, not a
    leak - as does the target amount, which is the number the player is
    trying to hit.
    """
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])

    if not reveal:
        doc["pool"] = [
            {k: v for k, v in item.items() if k not in ("price", "base_price")}
            for item in doc.get("pool", [])
        ]
        doc.pop("secret", None)

    return doc


def serialize_session(doc):
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    return doc
