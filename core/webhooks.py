from djstripe.event_handlers import djstripe_receiver
from djstripe.models import Customer, Event, Price, Product, Subscription
from sentry_sdk import logger

from core.models import Profile, ProfileStates


@djstripe_receiver("customer.subscription.created")
def handle_created_subscription(**kwargs):
    logger.info(
        "[Stripe Webhooks] handle_created_subscription webhook received",
        extra={
            "kwargs": kwargs,
        },
    )

    event_id = kwargs["event"].id
    event = Event.objects.get(id=event_id)

    customer = Customer.objects.get(id=event.data["object"]["customer"])
    subscription = Subscription.objects.get(id=event.data["object"]["id"])

    product_id = subscription.plan.product
    product = Product.objects.get(id=product_id)

    profile = Profile.objects.get(customer=customer)
    profile.subscription = subscription
    profile.product = product
    profile.save(update_fields=["subscription", "product"])

    profile.track_state_change(
        to_state=ProfileStates.SUBSCRIBED,
        metadata={
            "event": "subscription_created",
            "subscription_id": subscription.id,
            "stripe_event_id": event_id,
        },
    )

    logger.info(
        "[Stripe Webhooks] Subscription created and state updated for profile",
        extra={
            "profile_id": profile.id,
            "webhook": "handle_created_subscription",
            "subscription_id": subscription.id,
            "event_id": event_id,
        },
    )


@djstripe_receiver("customer.subscription.updated")
def handle_updated_subscription(**kwargs):
    logger.info(
        "[Stripe Webhooks] handle_updated_subscription webhook received",
        extra={
            "kwargs": kwargs,
        },
    )
    event_id = kwargs["event"].id
    event = Event.objects.get(id=event_id)

    subscription_data = event.data["object"]

    customer_id = subscription_data["customer"]
    subscription_id = subscription_data["id"]

    customer = Customer.objects.get(id=customer_id)
    subscription = Subscription.objects.get(id=subscription_id)
    profile = Profile.objects.get(customer=customer)

    if (
        subscription_data.get("cancel_at_period_end")
        and subscription_data.get("cancellation_details", {}).get("reason")
        == "cancellation_requested"
    ):
        # The subscription has been cancelled and will end at the end of the current period
        profile.track_state_change(
            to_state=ProfileStates.CANCELLED,
            metadata={
                "event": "subscription_cancelled",
                "subscription_id": subscription_id,
                "cancel_at": subscription_data.get("cancel_at"),
                "current_period_end": subscription_data.get("current_period_end"),
                "cancellation_feedback": subscription_data.get("cancellation_details", {}).get(
                    "feedback"
                ),
                "cancellation_comment": subscription_data.get("cancellation_details", {}).get(
                    "comment"
                ),
            },
        )

        logger.info(
            "[Stripe Webhooks] Subscription cancelled for profile.",
            extra={
                "profile_id": profile.id,
                "webhook": "handle_updated_subscription",
                "subscription_id": subscription_id,
                "end_date": subscription_data.get("current_period_end"),
            },
        )

    profile.subscription = subscription
    profile.save(update_fields=["subscription"])


@djstripe_receiver("customer.subscription.deleted")
def handle_deleted_subscription(**kwargs):
    logger.info(
        "[Stripe Webhooks] handle_deleted_subscription webhook received",
        extra={
            "kwargs": kwargs,
        },
    )
    event_id = kwargs["event"].id
    event = Event.objects.get(id=event_id)

    subscription_data = event.data["object"]
    customer_id = subscription_data["customer"]
    subscription_id = subscription_data["id"]

    customer = Customer.objects.get(id=customer_id)
    profile = Profile.objects.get(customer=customer)

    profile.track_state_change(
        to_state=ProfileStates.CHURNED,
        metadata={
            "event": "subscription_deleted",
            "subscription_id": subscription_id,
            "ended_at": subscription_data.get("ended_at"),
        },
    )

    profile.subscription = None
    profile.save(update_fields=["subscription"])

    logger.info(
        "Subscription deleted for profile.",
        profile_id=profile.id,
        subscription_id=subscription_id,
        ended_at=subscription_data.get("ended_at"),
    )

    # TODO: Implement any necessary clean-up or follow-up actions
    # For example: Revoke access to paid features, send a farewell email, etc.


@djstripe_receiver("checkout.session.completed")
def handle_checkout_completed(**kwargs):
    logger.info(
        "[Stripe Webhooks] handle_checkout_completed webhook received",
        extra={
            "kwargs": kwargs,
        },
    )
    event_id = kwargs["event"].id
    event = Event.objects.get(id=event_id)

    checkout_data = event.data["object"]
    customer_id = checkout_data.get("customer")
    checkout_id = checkout_data.get("id")
    # subscription_id = checkout_data.get("subscription")
    payment_status = checkout_data.get("payment_status")
    # mode = checkout_data.get("mode")  # 'subscription', 'payment', or 'setup'

    # Get metadata from checkout
    metadata = checkout_data.get("metadata", {})
    price_id = metadata.get("price_id")

    if payment_status != "paid":
        logger.warning(
            "[Stripe Webhooks] Checkout completed but payment not successful",
            extra={
                "event_id": event_id,
                "checkout_id": checkout_id,
                "payment_status": payment_status,
            },
        )
        return

    customer = Customer.objects.get(id=customer_id)
    profile = Profile.objects.get(customer=customer)

    update_fields = []

    # One-time payment checkout
    amount_total = checkout_data.get("amount_total")
    currency = checkout_data.get("currency")
    payment_intent = checkout_data.get("payment_intent")

    # Get the product associated with the price
    product = None
    product_data = {}

    if price_id:
        price = Price.objects.get(id=price_id)
        product = price.product

        # Update profile with product
        profile.product = product
        update_fields.append("product")

        product_data = {"product_id": product.id, "product_name": product.name}

    if update_fields:
        profile.save(update_fields=update_fields)

    profile.track_state_change(
        to_state=ProfileStates.SUBSCRIBED,
        metadata={
            "event": "checkout_payment_completed",
            "payment_intent": payment_intent,
            "checkout_id": checkout_id,
            "amount": amount_total,
            "currency": currency,
            "price_id": price_id,
            "stripe_event_id": event_id,
            **product_data,
        },
    )

    logger.info(
        "[Stripe Webhooks] User completed one-time payment",
        extra={
            "profile_id": profile.id,
            "payment_intent": payment_intent,
            "checkout_id": checkout_id,
            "amount": amount_total,
            "currency": currency,
            "metadata": metadata,
        },
    )
