"""Validate Shippo-compatible address objects without restricting extensions."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from shippo_integration.schemas.error import BusinessErrorCode


class AddressSchema(BaseModel):
    """Represent known Shippo address fields while preserving provider extras.

    Fields remain optional because this generic model is also useful for partial
    provider objects and address-validation responses. Shipment completeness is
    enforced by ``ShippingQuoteRequestSchema``, not by this reusable schema.
    Unknown fields are retained because Shippo may add provider extensions.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str | None = Field(default=None, min_length=1)
    company: str | None = None
    street1: str | None = Field(default=None, min_length=1)
    street2: str | None = None
    city: str | None = Field(default=None, min_length=1)
    state: str | None = Field(default=None, min_length=1)
    zip: str | None = Field(default=None, min_length=1)
    # Generic addresses default to US; shipping additionally rejects non-US data.
    country: str | None = Field(default="US", min_length=2, max_length=2)
    phone: str | None = None
    email: str | None = None
    # The Python name avoids BaseModel.validate; the alias preserves Shippo's key.
    validate_address: bool | None = Field(default=None, alias="validate")


class AddressValidationResult(BaseModel):
    """Represent a valid address, invalid address, or Shippo service failure.

    API boundaries can serialize the result with
    ``model_dump(exclude_unset=True)`` while application code uses typed fields.
    Legacy address fields remain available on successful and failed results.
    ``error_code`` and ``message`` are set only for invalid addresses or service
    failures, so exclude-unset serialization preserves the established wire shape.
    """

    model_config = ConfigDict(extra="forbid")

    success: bool
    valid: bool
    zip: str | None
    is_residential: bool | None
    messages: list[Any] = Field(default_factory=list)
    error_code: BusinessErrorCode | None = None
    message: str | None = None