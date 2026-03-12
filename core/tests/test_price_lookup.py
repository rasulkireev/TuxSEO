from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core import views


def test_get_price_for_product_name_falls_back_to_yearly_stripe_prices():
    product_name = "Pro - Yearly"
    stripe_price = {"id": "price_123", "product": SimpleNamespace(name=product_name)}

    with (
        patch.object(views.djstripe_models.Price.objects, "select_related") as mock_select_related,
        patch.object(views.stripe.Price, "list") as mock_stripe_list,
        patch.object(views.djstripe_models.Price, "sync_from_stripe_data") as mock_sync,
    ):
        mock_select_related.return_value.get.side_effect = views.djstripe_models.Price.DoesNotExist
        mock_stripe_list.return_value.auto_paging_iter.return_value = [stripe_price]
        mock_sync.return_value = "synced_price"

        result = views.get_price_for_product_name(product_name)

    assert result == "synced_price"
    mock_stripe_list.assert_called_once_with(active=True, expand=["data.product"], limit=100)
    mock_sync.assert_called_once_with(stripe_price)


def test_get_price_for_product_name_raises_when_price_is_missing():
    with (
        patch.object(views.djstripe_models.Price.objects, "select_related") as mock_select_related,
        patch.object(views.stripe.Price, "list") as mock_stripe_list,
    ):
        mock_select_related.return_value.get.side_effect = views.djstripe_models.Price.DoesNotExist
        mock_stripe_list.return_value.auto_paging_iter.return_value = []

        with pytest.raises(views.djstripe_models.Price.DoesNotExist):
            views.get_price_for_product_name("Pro - Yearly")
