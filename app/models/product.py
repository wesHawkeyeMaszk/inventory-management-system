REQUIRED_FIELDS = ["product_name", "product_category", "price", "available_quantity"]
OPTIONAL_FIELDS = {"description"}

# Fields the API itself hands back in responses (server-generated ID,
# timestamps, Mongo's _id). Silently dropped rather than rejected on input,
# so a client that fetches a product, edits it locally, and PUTs the whole
# thing back doesn't get a 422 for echoing back fields it was never meant
# to set.
METADATA_FIELDS = {"_id", "product_id", "created_at", "updated_at"}

SETTABLE_FIELDS = set(REQUIRED_FIELDS) | OPTIONAL_FIELDS


def _reject_unknown_fields(data):
    unexpected = set(data.keys()) - SETTABLE_FIELDS - METADATA_FIELDS
    if unexpected:
        return f"Unexpected field(s): {', '.join(sorted(unexpected))}"
    return None


def validate_product(data):
    """Validate and coerce a full product payload (create). Returns
    (cleaned_data, error_str).

    Returns a new dict rather than mutating the input, so callers that hold
    onto the original payload (e.g. bulk create iterating over request data)
    aren't surprised by in-place type coercion.
    """
    err = _reject_unknown_fields(data)
    if err:
        return None, err

    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        return None, f"Missing required fields: {', '.join(missing)}"

    cleaned = {k: v for k, v in data.items() if k in SETTABLE_FIELDS}

    try:
        cleaned["price"] = float(cleaned["price"])
    except (ValueError, TypeError):
        return None, "price must be a number"

    try:
        cleaned["available_quantity"] = int(cleaned["available_quantity"])
    except (ValueError, TypeError):
        return None, "available_quantity must be an integer"

    if cleaned["price"] < 0:
        return None, "price must be non-negative"
    if cleaned["available_quantity"] < 0:
        return None, "available_quantity must be non-negative"

    cleaned.setdefault("description", "")
    return cleaned, None


def validate_product_update(data):
    """Validate a partial update payload (PUT). Unlike validate_product, no
    field is required - only the fields present are checked and applied.
    """
    err = _reject_unknown_fields(data)
    if err:
        return None, err

    cleaned = {k: v for k, v in data.items() if k in SETTABLE_FIELDS}

    if "price" in cleaned:
        try:
            cleaned["price"] = float(cleaned["price"])
        except (ValueError, TypeError):
            return None, "price must be a number"
        if cleaned["price"] < 0:
            return None, "price must be non-negative"

    if "available_quantity" in cleaned:
        try:
            cleaned["available_quantity"] = int(cleaned["available_quantity"])
        except (ValueError, TypeError):
            return None, "available_quantity must be an integer"
        if cleaned["available_quantity"] < 0:
            return None, "available_quantity must be non-negative"

    return cleaned, None


def serialize_product(doc):
    """Convert a MongoDB document to a JSON-serialisable dict."""
    doc["_id"] = str(doc["_id"])
    return doc
