"""Pydantic contracts for generic Shippo service inputs and outputs."""

from shippo_integration.schemas.address import AddressSchema, AddressValidationResult
from shippo_integration.schemas.error import BusinessErrorCode, BusinessErrorSchema
from shippo_integration.schemas.parcel import ParcelSchema
from shippo_integration.schemas.shipping_quote import (
    ShippingQuoteRequestSchema,
    ShippingErrorResult,
    ShippingQuoteResult,
)

__all__ = [
    "AddressSchema",
    "AddressValidationResult",
    "BusinessErrorCode",
    "BusinessErrorSchema",
    "ParcelSchema",
    "ShippingQuoteRequestSchema",
    "ShippingErrorResult",
    "ShippingQuoteResult",
]