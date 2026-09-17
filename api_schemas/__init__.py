"""Pydantic contracts exposed by the local HTTP integration service."""

from api_schemas.address_validation import (
    AddressValidationRequestSchema,
    AddressValidationResponseSchema,
)
from api_schemas.health import HealthResponseSchema
from api_schemas.shipping_quote import (
    ShippingQuoteErrorResponseSchema,
    ShippingQuoteRequestSchema,
    ShippingQuoteResponseSchema,
    ShippingQuoteSuccessResponseSchema,
)

__all__ = [
    "AddressValidationRequestSchema",
    "AddressValidationResponseSchema",
    "HealthResponseSchema",
    "ShippingQuoteErrorResponseSchema",
    "ShippingQuoteRequestSchema",
    "ShippingQuoteResponseSchema",
    "ShippingQuoteSuccessResponseSchema",
]