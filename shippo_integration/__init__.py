"""Internal Shippo integration modules used by this repository.

This namespace organizes configuration, HTTP transport, and generic Shippo
operations. It is not published or installed as a third-party package.
"""

from shippo_integration.client import ShippoClient
from shippo_integration.exceptions import (
    ShippoAPIError,
    ShippoConfigurationError,
    ShippoResponseError,
    ShippoTimeoutError,
)

__all__ = [
    "ShippoAPIError",
    "ShippoClient",
    "ShippoConfigurationError",
    "ShippoResponseError",
    "ShippoTimeoutError",
]