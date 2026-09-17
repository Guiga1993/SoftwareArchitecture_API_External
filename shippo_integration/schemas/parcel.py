"""Validate Shippo-compatible parcel objects and preserve provider extensions."""

from pydantic import BaseModel, ConfigDict


# Preserve the caller's representation: Shippo accepts numeric measurements as
# strings, while internal callers may naturally provide integers or floats.
Measurement = str | int | float


class ParcelSchema(BaseModel):
    """Represent known Shippo parcel measurements and unit fields.

    Known values accept their existing string or numeric representation so
    schema validation does not alter the HTTP payload supplied by callers.
    Fields are optional for compatibility with partial provider objects. Shippo
    accepts distance units such as ``in``/``cm`` and mass units such as
    ``lb``/``oz``/``kg``/``g``; provider validation remains authoritative.
    ``template`` may identify a predefined Shippo parcel instead of dimensions.
    """

    model_config = ConfigDict(extra="allow")

    length: Measurement | None = None
    width: Measurement | None = None
    height: Measurement | None = None
    distance_unit: str | None = None
    weight: Measurement | None = None
    mass_unit: str | None = None
    template: str | None = None