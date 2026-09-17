"""Build Shippo address-validation requests and return typed business results.

The service owns payload construction and defensive provider-response parsing.
Transport and retry behavior remain inside ``ShippoClient``.
"""

from typing import Any

from shippo_integration.client import ShippoClient
from shippo_integration.schemas.address import AddressSchema, AddressValidationResult
from shippo_integration.services.error_mapping import (
    SHIPPO_SERVICE_EXCEPTIONS,
    map_shippo_exception,
)


def validate_address(
    name: str,
    street1: str,
    city: str,
    state: str,
    zip_code: str,
    country: str = "US",
    *,
    client: ShippoClient | None = None,
    correlation_id: str | None = None,
) -> AddressValidationResult:
    """Validate one address and return provider-independent result fields.

    Args:
        name: Person or company associated with the address.
        street1: Primary street address line.
        city: Address city.
        state: State or region code.
        zip_code: Postal code supplied by the caller.
        country: ISO country code; defaults to the United States.
        client: Optional client used for dependency injection and unit testing.
        correlation_id: Optional HTTP request identifier propagated to Shippo.

    Returns:
        Typed address validity, normalization, and structured failure details.

    Notes:
        Adapter exceptions are converted to stable business error codes. Input
        validation errors still raise before any network operation.
    """
    address = AddressSchema(
        name=name,
        street1=street1,
        city=city,
        state=state,
        zip=zip_code,
        country=country,
        validate_address=True,
    )
    payload = address.model_dump(
        by_alias=True,
        exclude_unset=True,
        exclude_none=True,
    )
    try:
        shippo_client = client or ShippoClient()
        if correlation_id is None:
            response = shippo_client.post("/addresses/", payload)
        else:
            response = shippo_client.post(
                "/addresses/",
                payload,
                correlation_id=correlation_id,
            )
    except SHIPPO_SERVICE_EXCEPTIONS as error:
        error_code, message = map_shippo_exception(error)
        return AddressValidationResult(
            success=False,
            error_code=error_code,
            message=message,
            valid=False,
            zip=None,
            is_residential=None,
            messages=[],
        )

    # Shippo may omit or alter optional validation metadata; defensive coercion
    # keeps the public result model stable without hiding transport failures.
    validation_results = response.get("validation_results", {})
    if not isinstance(validation_results, dict):
        validation_results = {}
    messages = validation_results.get("messages", [])
    if not isinstance(messages, list):
        messages = []

    valid = bool(validation_results.get("is_valid", False))
    if valid:
        return AddressValidationResult(
            success=True,
            valid=True,
            zip=response.get("zip"),
            is_residential=response.get("is_residential"),
            messages=messages,
        )

    return AddressValidationResult(
        success=False,
        error_code="INVALID_ADDRESS",
        message="Shippo could not validate the supplied address.",
        valid=False,
        zip=response.get("zip"),
        is_residential=response.get("is_residential"),
        messages=messages,
    )