from pathlib import Path


PRICING_TEMPLATE_PATH = Path("frontend/templates/pages/pricing.html")
SETTINGS_TEMPLATE_PATH = Path("frontend/templates/pages/user-settings.html")


def test_pricing_template_uses_free_and_pro_only_with_current_checkout_targets():
    content = PRICING_TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "Free" in content
    assert "Pro" in content
    assert "$99" in content
    assert "$990" in content
    assert "product_name='Pro - Monthly'" in content
    assert "product_name='Pro - Yearly'" in content

    for legacy_copy in [
        "Starter",
        "Growth",
        "Agency",
        "Pro - Starter",
        "Pro - Growth",
        "Pro - Agency",
        "$79",
        "$199",
        "$299",
    ]:
        assert legacy_copy not in content


def test_user_settings_template_shows_updated_pro_prices_and_checkout_targets():
    content = SETTINGS_TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "$99" in content
    assert "$990" in content
    assert "product_name='Pro - Monthly'" in content
    assert "product_name='Pro - Yearly'" in content
    assert "$100" not in content
    assert "$1000" not in content
