"""Define the liveness response exposed by GET /health."""

from typing import Literal

from pydantic import BaseModel


class HealthResponseSchema(BaseModel):
    """Report HTTP process liveness without probing Shippo readiness.

    Keeping liveness independent from credentials and provider availability
    lets operators distinguish a running service from a configured dependency.
    """

    status: Literal["up"] = "up"
    service: Literal["shippo-integration"] = "shippo-integration"