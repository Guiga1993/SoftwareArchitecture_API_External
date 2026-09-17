"""Load and validate Shippo settings for the external integration project.

Process environment values take precedence over the ignored repository-level
``.env`` file. This supports local development without overriding deployment
secret stores or command-line configuration.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from shippo_integration.exceptions import ShippoConfigurationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

# Transport defaults are intentionally conservative. Timeout controls one HTTP
# attempt; max_attempts includes the initial attempt; backoff is the exponential
# base; Retry-After is capped so provider throttling cannot block indefinitely.
DEFAULT_SHIPPO_BASE_URL = "https://api.goshippo.com"
DEFAULT_SHIPPO_TIMEOUT_SECONDS = 30.0
DEFAULT_SHIPPO_MAX_ATTEMPTS = 3
DEFAULT_SHIPPO_BACKOFF_SECONDS = 0.5
DEFAULT_SHIPPO_MAX_RETRY_AFTER_SECONDS = 30.0
DEFAULT_INTEGRATION_API_HOST = "127.0.0.1"
DEFAULT_INTEGRATION_API_PORT = 8001
DEFAULT_INTEGRATION_API_DEBUG = False


@dataclass(frozen=True)
class ShippoSettings:
    """Immutable connection and retry policy used by ``ShippoClient``.

    ``max_attempts`` includes the first request. ``backoff_seconds`` is the base
    for exponential GET/429 delays, and ``max_retry_after_seconds`` limits how
    long a provider-supplied Retry-After value may pause execution.
    """

    api_key: str
    base_url: str
    timeout_seconds: float
    max_attempts: int = DEFAULT_SHIPPO_MAX_ATTEMPTS
    backoff_seconds: float = DEFAULT_SHIPPO_BACKOFF_SECONDS
    max_retry_after_seconds: float = DEFAULT_SHIPPO_MAX_RETRY_AFTER_SECONDS


@dataclass(frozen=True)
class IntegrationAPISettings:
    """Immutable local HTTP server settings used only by root ``app.py``."""

    host: str = DEFAULT_INTEGRATION_API_HOST
    port: int = DEFAULT_INTEGRATION_API_PORT
    debug: bool = DEFAULT_INTEGRATION_API_DEBUG


def load_shippo_environment(env_file: Path | None = None) -> None:
    """Load local settings without overriding existing environment variables.

    Args:
        env_file: Optional dotenv path; defaults to the repository-level ``.env``.
    """
    load_dotenv(dotenv_path=env_file or DEFAULT_ENV_FILE, override=False)


def get_shippo_settings() -> ShippoSettings:
    """Read and validate Shippo settings from the current environment.

    Returns:
        Validated immutable Shippo settings.

    Raises:
        ShippoConfigurationError: The API key, timeout, attempt count, backoff,
            or Retry-After cap is missing or invalid.
    """
    load_shippo_environment()
    api_key = os.getenv("SHIPPO_API_KEY")
    if not api_key:
        raise ShippoConfigurationError(
            "SHIPPO_API_KEY is not configured in the process environment or .env file."
        )

    # Parse the complete transport policy together so construction is atomic:
    # callers never receive settings with only part of the retry policy applied.
    try:
        timeout_seconds = float(
            os.getenv("SHIPPO_TIMEOUT_SECONDS", DEFAULT_SHIPPO_TIMEOUT_SECONDS)
        )
        max_attempts = int(
            os.getenv("SHIPPO_MAX_ATTEMPTS", DEFAULT_SHIPPO_MAX_ATTEMPTS)
        )
        backoff_seconds = float(
            os.getenv("SHIPPO_BACKOFF_SECONDS", DEFAULT_SHIPPO_BACKOFF_SECONDS)
        )
        max_retry_after_seconds = float(
            os.getenv(
                "SHIPPO_MAX_RETRY_AFTER_SECONDS",
                DEFAULT_SHIPPO_MAX_RETRY_AFTER_SECONDS,
            )
        )
    except ValueError as exc:
        raise ShippoConfigurationError(
            "Shippo timeout and retry settings must be numeric."
        ) from exc

    if timeout_seconds <= 0:
        raise ShippoConfigurationError(
            "SHIPPO_TIMEOUT_SECONDS must be greater than zero."
        )
    if max_attempts <= 0:
        raise ShippoConfigurationError(
            "SHIPPO_MAX_ATTEMPTS must be greater than zero."
        )
    if backoff_seconds < 0:
        raise ShippoConfigurationError(
            "SHIPPO_BACKOFF_SECONDS cannot be negative."
        )
    if max_retry_after_seconds <= 0:
        raise ShippoConfigurationError(
            "SHIPPO_MAX_RETRY_AFTER_SECONDS must be greater than zero."
        )

    base_url = os.getenv("SHIPPO_BASE_URL", DEFAULT_SHIPPO_BASE_URL).rstrip("/")
    return ShippoSettings(
        api_key,
        base_url,
        timeout_seconds,
        max_attempts,
        backoff_seconds,
        max_retry_after_seconds,
    )


def get_integration_api_settings() -> IntegrationAPISettings:
    """Read and validate local HTTP server settings from the environment.

    Returns:
        Host, port, and debug settings used when executing ``python app.py``.

    Raises:
        ShippoConfigurationError: Port or debug values are invalid. This does
            not inspect Shippo credentials or warehouse configuration.
    """
    load_shippo_environment()
    host = os.getenv("INTEGRATION_API_HOST", DEFAULT_INTEGRATION_API_HOST).strip()
    if not host:
        host = DEFAULT_INTEGRATION_API_HOST

    try:
        port = int(os.getenv("INTEGRATION_API_PORT", DEFAULT_INTEGRATION_API_PORT))
    except ValueError as exc:
        raise ShippoConfigurationError(
            "INTEGRATION_API_PORT must be an integer."
        ) from exc
    if not 1 <= port <= 65535:
        raise ShippoConfigurationError(
            "INTEGRATION_API_PORT must be between 1 and 65535."
        )

    debug_text = os.getenv(
        "INTEGRATION_API_DEBUG",
        str(DEFAULT_INTEGRATION_API_DEBUG),
    ).strip().lower()
    boolean_values = {
        "true": True,
        "1": True,
        "yes": True,
        "on": True,
        "false": False,
        "0": False,
        "no": False,
        "off": False,
    }
    if debug_text not in boolean_values:
        raise ShippoConfigurationError(
            "INTEGRATION_API_DEBUG must be a boolean value."
        )

    return IntegrationAPISettings(host, port, boolean_values[debug_text])