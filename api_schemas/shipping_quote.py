"""Define strict HTTP contracts for complete US shipment quote operations.

These models validate untrusted JSON at the service boundary. Reusable internal
provider models remain permissive so Shippo extensions can round-trip unchanged.
"""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

from shippo_integration.schemas.error import BusinessErrorCode
from shippo_integration.schemas.shipping_quote import (
    ShippingErrorResult,
    ShippingQuoteResult,
)


Measurement = str | int | float


class ShippingAddressSchema(BaseModel):
    """Require one complete caller-owned US shipping address over HTTP."""

    name: str = Field(min_length=2, max_length=150)
    street1: str = Field(min_length=3, max_length=150)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(pattern=r"^[A-Za-z]{2}$")
    zip: str = Field(pattern=r"^\d{5}(?:-\d{4})?$")
    country: str = Field(default="US", min_length=2, max_length=2)

    @field_validator("name", "street1", "city")
    @classmethod
    def trim_text_fields(cls, value: str) -> str:
        """Trim caller text and reject values containing only whitespace."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("shipping address fields must not be blank")
        return normalized

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        """Normalize the two-letter shipping state code to uppercase."""
        return value.upper()

    @field_validator("country")
    @classmethod
    def require_us_country(cls, value: str) -> str:
        """Normalize US and reject international quote requests."""
        normalized = value.upper()
        if normalized != "US":
            raise ValueError("country must be US; international shipping is unsupported")
        return normalized


class ParcelRequestSchema(BaseModel):
    """Require one complete parcel with explicit Shippo-compatible units."""

    length: Measurement
    width: Measurement
    height: Measurement
    distance_unit: Literal["in", "cm"]
    weight: Measurement
    mass_unit: Literal["lb", "oz", "kg", "g"]

    @field_validator("length", "width", "height", "weight")
    @classmethod
    def require_positive_measurement(cls, value: Measurement) -> Measurement:
        """Reject nonnumeric, zero, and negative parcel measurements."""
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("parcel measurements must be numeric") from exc
        if not math.isfinite(numeric_value) or numeric_value <= 0:
            raise ValueError("parcel measurements must be greater than zero")
        return value


class ShippingQuoteRequestSchema(BaseModel):
    """Validate complete caller-owned addresses and one or more parcels.

    Unknown HTTP fields are rejected so backend-to-integration contract drift
    fails before provider payload construction.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "address_from": {
                    "name": "Origin Company",
                    "street1": "123 Origin Street",
                    "city": "Torrance",
                    "state": "CA",
                    "zip": "90504",
                    "country": "US",
                },
                "address_to": {
                    "name": "Customer Company",
                    "street1": "456 Destination Street",
                    "city": "Atlanta",
                    "state": "GA",
                    "zip": "30301",
                    "country": "US",
                },
                "parcels": [
                    {
                        "length": "48",
                        "width": "40",
                        "height": "60",
                        "distance_unit": "in",
                        "weight": "12",
                        "mass_unit": "lb",
                    }
                ],
            }
        },
    )

    address_from: ShippingAddressSchema
    address_to: ShippingAddressSchema
    parcels: list[ParcelRequestSchema] = Field(min_length=1)


class ShippingQuoteSuccessResponseSchema(BaseModel):
    """Expose the cheapest rate selected by the shipping service."""

    success: Literal[True]
    carrier: str | None
    service: str | None
    amount: str | None
    currency: str | None
    estimated_days: int | None

    @classmethod
    def from_result(
        cls,
        result: ShippingQuoteResult,
    ) -> "ShippingQuoteSuccessResponseSchema":
        """Adapt an internal successful quote without changing its fields."""
        return cls.model_validate(result.model_dump(exclude_unset=True))


class ShippingQuoteErrorResponseSchema(BaseModel):
    """Expose structured shipping business and provider failures."""

    success: Literal[False]
    error_code: BusinessErrorCode
    message: str
    shippo_messages: list[dict[str, str]] = Field(default_factory=list)

    @classmethod
    def from_result(
        cls,
        result: ShippingErrorResult,
    ) -> "ShippingQuoteErrorResponseSchema":
        """Adapt an internal shipping error without exposing provider internals."""
        return cls.model_validate(result.model_dump(exclude_unset=True))


class ShippingQuoteResponseSchema(
    RootModel[ShippingQuoteSuccessResponseSchema | ShippingQuoteErrorResponseSchema]
):
    """Document the literal-discriminated success and error response union.

    Business outcomes such as ``NO_RATES`` use the error shape with HTTP 200,
    while technical error codes use the same body shape with 5xx statuses.
    """