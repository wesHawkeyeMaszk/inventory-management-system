from app.models.product import validate_product


def test_valid_product_is_cleaned_and_coerced():
    data = {
        "product_name": "Widget",
        "product_category": "Tools",
        "price": "9.99",
        "available_quantity": "100",
    }
    cleaned, err = validate_product(data)

    assert err is None
    assert cleaned["price"] == 9.99
    assert cleaned["available_quantity"] == 100
    assert cleaned["description"] == ""


def test_validate_product_does_not_mutate_input():
    data = {
        "product_name": "Widget",
        "product_category": "Tools",
        "price": "9.99",
        "available_quantity": "100",
    }
    original = dict(data)

    validate_product(data)

    assert data == original
    assert isinstance(data["price"], str)
    assert isinstance(data["available_quantity"], str)


def test_missing_required_field():
    cleaned, err = validate_product({"product_name": "Widget"})
    assert cleaned is None
    assert "product_category" in err


def test_negative_price_rejected():
    data = {
        "product_name": "Widget",
        "product_category": "Tools",
        "price": -1,
        "available_quantity": 1,
    }
    cleaned, err = validate_product(data)
    assert cleaned is None
    assert "non-negative" in err


def test_non_numeric_price_rejected():
    data = {
        "product_name": "Widget",
        "product_category": "Tools",
        "price": "not-a-number",
        "available_quantity": 1,
    }
    cleaned, err = validate_product(data)
    assert cleaned is None
    assert "price must be a number" == err
