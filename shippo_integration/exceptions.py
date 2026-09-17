"""Define safe exception categories exposed by the Shippo transport adapter.

These exceptions preserve failure categories for the service layer without
exposing credentials, raw provider responses, or low-level request details.
"""


class ShippoConfigurationError(ValueError):
    """Report missing or invalid credentials and transport configuration.

    This error can occur before any network request while constructing a
    ``ShippoClient`` from environment-derived settings.
    """


class ShippoTimeoutError(Exception):
    """Report a terminal timeout after applying the method-aware retry policy.

    GET operations may reach this error after retries; ambiguous POST timeouts
    are terminal immediately to avoid creating duplicate provider resources.
    """


class ShippoAPIError(Exception):
    """Report terminal network failures or unsuccessful Shippo HTTP statuses."""


class ShippoResponseError(Exception):
    """Report successful HTTP responses that are not valid JSON objects.

    Response bodies are deliberately excluded from the public exception text
    so callers and logs cannot accidentally expose provider data.
    """