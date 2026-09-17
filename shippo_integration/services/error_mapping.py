"""Translate Shippo adapter exceptions into stable business failure details."""

from shippo_integration.exceptions import (
    ShippoAPIError,
    ShippoConfigurationError,
    ShippoResponseError,
    ShippoTimeoutError,
)
from shippo_integration.schemas.error import BusinessErrorCode


# Both public services catch this exact adapter boundary. Configuration and
# timeout errors retain dedicated business codes; HTTP/network/response errors
# intentionally share SHIPPO_FAILURE to keep the consumer contract compact.
SHIPPO_SERVICE_EXCEPTIONS = (
    ShippoConfigurationError,
    ShippoTimeoutError,
    ShippoAPIError,
    ShippoResponseError,
)


def map_shippo_exception(
    error: Exception,
) -> tuple[BusinessErrorCode, str]:
    """Return a safe business code and message for a Shippo adapter exception.

    Args:
        error: Exception raised during client construction or an HTTP operation.

    Returns:
        A stable error code and human-readable message that expose no secrets or
        raw provider response content.
    """
    if isinstance(error, ShippoConfigurationError):
        return "CONFIGURATION_ERROR", "Shippo is not configured correctly."
    if isinstance(error, ShippoTimeoutError):
        return "SHIPPO_TIMEOUT", "Shippo did not respond before the request timed out."
    return "SHIPPO_FAILURE", "Unable to complete the request with Shippo."