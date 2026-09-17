"""Validate provider-ready shipments and model typed quote service results.

The aggregate closes completeness gaps intentionally left in reusable address
and parcel models before any payload is handed to ``ShippoClient``.
"""

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shippo_integration.schemas.address import AddressSchema
from shippo_integration.schemas.error import BusinessErrorSchema
from shippo_integration.schemas.parcel import ParcelSchema


# This integration intentionally supports domestic United States shipping only.
# The aggregate validator writes this code onto both outbound addresses.
SHIPPO_COUNTRY_CODE = "US"


class ShippingQuoteRequestSchema(BaseModel):
    """Require complete US origin, destination, and parcel data for Shippo.

    Unlike generic ``AddressSchema`` objects, shipment addresses must contain
    identity, street, city, state, and ZIP fields. At least one parcel is also
    required before the service is allowed to call Shippo.
    """

    model_config = ConfigDict(extra="allow")

    address_from: AddressSchema
    address_to: AddressSchema
    parcels: list[ParcelSchema] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_complete_addresses(self):
        """Reject incomplete addresses/parcels and normalize US countries.

        The validator reports missing fields as ``address_from.field`` or
        ``address_to.field`` and mutates both nested models to ``country='US'``.
        This side effect makes the application-owned country rule explicit in
        the final Shippo payload even when callers omit country.
        """
        # Generic AddressSchema instances may be partial; shipment creation may not.
        required_fields = ("name", "street1", "city", "state", "zip")
        missing_fields = []
        for address_name in ("address_from", "address_to"):
            address = getattr(self, address_name)
            for field_name in required_fields:
                value = getattr(address, field_name)
                if value is None or not value.strip():
                    missing_fields.append(f"{address_name}.{field_name}")

            if address.country and address.country.upper() != SHIPPO_COUNTRY_CODE:
                raise ValueError(
                    f"{address_name}.country must be {SHIPPO_COUNTRY_CODE}; "
                    "international shipping is not supported."
                )
            # Country is an application rule, not caller-controlled quote data.
            address.country = SHIPPO_COUNTRY_CODE

        if missing_fields:
            raise ValueError(
                "Missing required shipping address fields: "
                + ", ".join(missing_fields)
            )

        # ParcelSchema preserves partial provider objects, so the aggregate owns
        # complete, finite, positive measurement and supported-unit validation.
        required_measurements = ("length", "width", "height", "weight")
        for index, parcel in enumerate(self.parcels):
            for field_name in required_measurements:
                value = getattr(parcel, field_name)
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"parcels.{index}.{field_name} must be a positive number"
                    ) from exc
                if not math.isfinite(numeric_value) or numeric_value <= 0:
                    raise ValueError(
                        f"parcels.{index}.{field_name} must be a positive number"
                    )
            if parcel.distance_unit not in {"in", "cm"}:
                raise ValueError(
                    f"parcels.{index}.distance_unit is not supported"
                )
            if parcel.mass_unit not in {"lb", "oz", "kg", "g"}:
                raise ValueError(f"parcels.{index}.mass_unit is not supported")
        return self


class ShippingQuoteResult(BaseModel):
    """Represent the cheapest available shipping rate selected by the service.

    ``success`` is a literal discriminator. Amount remains text to preserve
    Shippo's decimal representation, while estimated delivery may be unknown.
    """

    model_config = ConfigDict(extra="forbid")

    success: Literal[True]
    carrier: str | None
    service: str | None
    amount: str | None
    currency: str | None
    estimated_days: int | None


class ShippingErrorResult(BusinessErrorSchema):
    """Represent a structured shipping failure with legacy provider messages.

    API boundaries can serialize this model with
    ``model_dump(exclude_unset=True)`` to retain the existing failure shape.
    Provider messages are normalized to source/message dictionaries and are
    independent per model instance through ``default_factory``.
    """

    shippo_messages: list[dict[str, Any]] = Field(default_factory=list)