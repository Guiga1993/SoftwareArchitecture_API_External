"""Create generic Shippo shipments and select the cheapest available rate."""

from collections.abc import Mapping
from typing import Any

from shippo_integration.client import ShippoClient
from shippo_integration.schemas.address import AddressSchema
from shippo_integration.schemas.parcel import ParcelSchema
from shippo_integration.schemas.shipping_quote import (
    SHIPPO_COUNTRY_CODE,
    ShippingErrorResult,
    ShippingQuoteRequestSchema,
    ShippingQuoteResult,
)
from shippo_integration.services.error_mapping import (
    SHIPPO_SERVICE_EXCEPTIONS,
    map_shippo_exception,
)


def _select_cheapest_rate(rates: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the Shippo rate with the lowest numeric amount.

    Shippo represents amounts as decimal strings. Conversion is used only for
    comparison; the selected result preserves the original amount text.
    """
    return min(rates, key=lambda rate: float(rate["amount"]))


def _extract_messages(response: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize optional Shippo messages to stable source/message pairs.

    Malformed non-list containers become an empty list. Non-dictionary entries
    are ignored, unknown fields are dropped, and values are converted to text so
    consumers receive one predictable shape on no-rate responses.
    """
    messages = response.get("messages", [])
    if not isinstance(messages, list):
        return []
    return [
        {
            "source": str(message.get("source", "Unknown")),
            "message": str(message.get("text", "")),
        }
        for message in messages
        if isinstance(message, dict)
    ]


def get_shipping_quote(
    address_from: AddressSchema | Mapping[str, Any],
    address_to: AddressSchema | Mapping[str, Any],
    parcels: list[ParcelSchema | Mapping[str, Any]],
    *,
    client: ShippoClient | None = None,
    correlation_id: str | None = None,
) -> ShippingQuoteResult | ShippingErrorResult:
    """Create a shipment and return its cheapest available Shippo rate.

    Args:
        address_from: Shippo origin address mapping or validated schema.
        address_to: Shippo destination address mapping or validated schema.
        parcels: One or more parcel mappings or validated schemas.
        client: Optional client used for dependency injection and unit testing.
        correlation_id: Optional HTTP request identifier propagated to Shippo.

    Returns:
        A typed successful quote or structured shipping error result.

    Raises:
        ValueError: No parcel was supplied.
        ValidationError: Either address is incomplete or outside the US.
    """
    if not parcels:
        raise ValueError("At least one parcel is required for a shipping quote.")

    quote_request = ShippingQuoteRequestSchema.model_validate(
        {
            "address_from": address_from,
            "address_to": address_to,
            "parcels": parcels,
        }
    )
    payload = quote_request.model_dump(
        by_alias=True,
        exclude_unset=True,
        exclude_none=True,
    )
    try:
        shippo_client = client or ShippoClient()
        if correlation_id is None:
            response = shippo_client.post("/shipments/", payload)
        else:
            response = shippo_client.post(
                "/shipments/",
                payload,
                correlation_id=correlation_id,
            )
    except SHIPPO_SERVICE_EXCEPTIONS as error:
        error_code, message = map_shippo_exception(error)
        return ShippingErrorResult(
            success=False,
            error_code=error_code,
            message=message,
            shippo_messages=[],
        )

    rates = response.get("rates", [])
    if isinstance(rates, list) and rates:
        try:
            cheapest_rate = _select_cheapest_rate(rates)
        except (KeyError, TypeError, ValueError):
            return ShippingErrorResult(
                success=False,
                error_code="SHIPPO_FAILURE",
                message="Unable to complete the request with Shippo.",
                shippo_messages=[],
            )

        service_level = cheapest_rate.get("servicelevel", {})
        if not isinstance(service_level, dict):
            service_level = {}
        return ShippingQuoteResult(
            success=True,
            carrier=cheapest_rate.get("provider", "Unknown"),
            service=service_level.get("name", "Unknown"),
            amount=cheapest_rate.get("amount"),
            currency=cheapest_rate.get("currency", "USD"),
            estimated_days=cheapest_rate.get("estimated_days"),
        )

    return ShippingErrorResult(
        success=False,
        error_code="NO_RATES",
        message="No shipping rates available.",
        shippo_messages=_extract_messages(response),
    )
