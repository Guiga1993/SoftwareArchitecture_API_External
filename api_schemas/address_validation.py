"""Define HTTP request and response contracts for address validation."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shippo_integration.schemas.address import AddressValidationResult
from shippo_integration.schemas.error import BusinessErrorCode


class AddressValidationRequestSchema(BaseModel):
    """Validate one complete US address submitted through HTTP JSON."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_name": "Customer Company",
                "street1": "123 Main Street",
                "city": "Atlanta",
                "state": "GA",
                "zip_code": "30301",
                "country": "US",
            }
        }
    )

    customer_name: str = Field(min_length=2, max_length=150)
    street1: str = Field(min_length=3, max_length=150)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(pattern=r"^[A-Za-z]{2}$")
    zip_code: str = Field(pattern=r"^\d{5}(?:-\d{4})?$")
    country: str = Field(default="US", min_length=2, max_length=2)

    @field_validator("customer_name", "street1", "city")
    @classmethod
    def trim_text_fields(cls, value: str) -> str:
        """Trim surrounding whitespace before invoking the business service."""
        return value.strip()

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        """Normalize the two-letter state code to uppercase."""
        return value.upper()

    @field_validator("country")
    @classmethod
    def require_us_country(cls, value: str) -> str:
        """Normalize US and reject international address-validation requests."""
        normalized = value.upper()
        if normalized != "US":
            raise ValueError("country must be US; international validation is unsupported")
        return normalized


class AddressValidationResponseSchema(BaseModel):
    """Expose a typed address result using HTTP-friendly field names."""

    success: bool
    valid: bool
    normalized_zip: str | None = None
    is_residential: bool | None = None
    messages: list[Any] = Field(default_factory=list)
    error_code: BusinessErrorCode | None = None
    message: str | None = None

    @classmethod
    def from_result(
        cls,
        result: AddressValidationResult,
    ) -> "AddressValidationResponseSchema":
        """Adapt the internal result while renaming ``zip`` to ``normalized_zip``."""
        values = result.model_dump(exclude_unset=True)
        values["normalized_zip"] = values.pop("zip", None)
        return cls.model_validate(values)