"""Define stable business error codes shared by Shippo service responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


# Stable codes are intended for caller branching; human-readable messages may
# evolve. NO_RATES/INVALID_ADDRESS are business outcomes, SHIPPO_TIMEOUT and
# SHIPPO_FAILURE are provider/transport failures, and CONFIGURATION_ERROR means
# required local settings are absent or invalid.
BusinessErrorCode = Literal[
    "NO_RATES",
    "INVALID_ADDRESS",
    "SHIPPO_TIMEOUT",
    "SHIPPO_FAILURE",
    "CONFIGURATION_ERROR",
]


class BusinessErrorSchema(BaseModel):
    """Represent the common machine-readable service failure envelope.

    ``success`` is fixed to false so error models cannot accidentally serialize
    as successful responses. Consumers should branch on ``error_code`` rather
    than matching the human-readable ``message``.
    """

    model_config = ConfigDict(extra="forbid")

    success: Literal[False] = False
    error_code: BusinessErrorCode
    message: str