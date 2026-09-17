"""Provide observable, retry-aware HTTP transport for Shippo operations.

This module centralizes URL normalization, authentication, timeouts, network
errors, rate limits, latency logging, and JSON decoding. GET requests retry
transient failures; POST requests retry only explicit rate-limit responses.
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

from shippo_integration.config import ShippoSettings, get_shippo_settings
from shippo_integration.exceptions import (
    ShippoAPIError,
    ShippoResponseError,
    ShippoTimeoutError,
)


logger = logging.getLogger(__name__)

# GET operations are safe to retry after transient transport/gateway failures.
# POST retries are deliberately limited to explicit rate limiting because an
# ambiguous timeout or gateway failure may already have created a Shippo object.
GET_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
POST_RETRYABLE_STATUS_CODES = frozenset({429})
GET_RETRYABLE_EXCEPTIONS = (
    requests.Timeout,
    requests.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
)


class ShippoClient:
    """Execute authenticated requests against configured Shippo endpoints.

    The class owns authentication headers and all transport concerns. Public
    callers use only ``get`` and ``post``; retries, correlation IDs, timing,
    response validation, and exception translation remain internal.
    """

    def __init__(self, settings: ShippoSettings | None = None) -> None:
        """Create a client from explicit or environment-derived settings.

        Args:
            settings: Optional immutable settings, primarily useful for tests or
                applications that do not use environment-based configuration.

        Raises:
            ShippoConfigurationError: Indirectly raised by ``get_shippo_settings``
                when required environment configuration is invalid.
        """
        self.settings = settings or get_shippo_settings()
        self.headers = {
            "Authorization": f"ShippoToken {self.settings.api_key}",
            "Content-Type": "application/json",
        }

    def _is_retryable_status(self, method: str, status_code: int) -> bool:
        """Return whether an HTTP status is safe to retry for the method.

        GET permits transient gateway and rate-limit retries. POST permits only
        429 because retrying an ambiguous POST could create duplicate resources.
        """
        retryable_statuses = (
            GET_RETRYABLE_STATUS_CODES
            if method == "GET"
            else POST_RETRYABLE_STATUS_CODES
        )
        return status_code in retryable_statuses

    def _backoff_delay(self, attempt: int) -> float:
        """Calculate exponential delay after a failed one-based attempt.

        With the default base, failures after attempts one and two wait 0.5 and
        1.0 seconds respectively before the next attempt.
        """
        return self.settings.backoff_seconds * (2 ** (attempt - 1))

    def _retry_after_delay(
        self,
        header_value: str | None,
        fallback_delay: float,
        correlation_id: str,
    ) -> float:
        """Resolve a bounded delay from a Retry-After header.

        Args:
            header_value: Delta seconds or an RFC 7231 HTTP-date from Shippo.
            fallback_delay: Exponential delay used when the header is absent or
                malformed.
            correlation_id: Request identifier included in malformed-header logs.

        Returns:
            A non-negative delay capped by ``max_retry_after_seconds``. Past
            dates become zero so the retry may proceed immediately.
        """
        if header_value is None:
            return min(fallback_delay, self.settings.max_retry_after_seconds)

        try:
            delay = float(header_value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(header_value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                delay = (retry_at - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                logger.warning(
                    "Malformed Retry-After header correlation_id=%s; "
                    "using exponential backoff",
                    correlation_id,
                )
                delay = fallback_delay

        return min(max(delay, 0.0), self.settings.max_retry_after_seconds)

    def _log_terminal_request(
        self,
        correlation_id: str,
        method: str,
        endpoint: str,
        attempts: int,
        started_at: float,
        outcome: str,
    ) -> None:
        """Log one safe terminal event with total monotonic latency.

        Only operational metadata is recorded. Credentials, headers, payloads,
        response bodies, query strings, and raw exception text are excluded.
        """
        latency_ms = (time.perf_counter() - started_at) * 1000
        logger.debug(
            "Shippo request finished correlation_id=%s method=%s endpoint=%s "
            "attempts=%d outcome=%s latency_ms=%.2f",
            correlation_id,
            method,
            endpoint,
            attempts,
            outcome,
            latency_ms,
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute one logical request with method-aware retries.

        One correlation ID is generated for the logical call and reused across
        attempts. GET retries transient transport errors and selected statuses;
        POST retries only 429. Terminal failures preserve the established
        ``ShippoTimeoutError``, ``ShippoAPIError``, and ``ShippoResponseError``
        contracts.

        Args:
            method: HTTP method used by the public wrapper.
            endpoint: Shippo path; a leading slash is optional.
            payload: Optional JSON object sent to Shippo.
            correlation_id: Optional caller request identifier. A UUID is
                generated when no identifier is supplied.

        Returns:
            The decoded object response from a successful request.

        Raises:
            ShippoTimeoutError: A timeout is not retryable or GET retries expire.
            ShippoAPIError: A network/HTTP failure is terminal.
            ShippoResponseError: A successful response is invalid JSON or is not
                a JSON object.
        """
        url = f"{self.settings.base_url}/{endpoint.lstrip('/')}"
        # Keep queries out of logs while preserving them in the actual request URL.
        normalized_endpoint = f"/{endpoint.lstrip('/').split('?', 1)[0]}"
        correlation_id = correlation_id or str(uuid.uuid4())
        # Copy stable authentication headers so correlation metadata cannot leak
        # into later logical calls made by this client instance.
        request_headers = {
            **self.headers,
            "X-Correlation-ID": correlation_id,
        }
        started_at = time.perf_counter()

        for attempt in range(1, self.settings.max_attempts + 1):
            logger.debug(
                "Shippo request attempt correlation_id=%s method=%s endpoint=%s "
                "attempt=%d/%d",
                correlation_id,
                method,
                normalized_endpoint,
                attempt,
                self.settings.max_attempts,
            )
            try:
                response = requests.request(
                    method,
                    url,
                    json=payload,
                    headers=request_headers,
                    timeout=self.settings.timeout_seconds,
                )
            except requests.Timeout as exc:
                # GET can be replayed after an ambiguous timeout; POST cannot,
                # because Shippo may have committed the resource already.
                can_retry = method == "GET" and attempt < self.settings.max_attempts
                if can_retry:
                    delay = self._backoff_delay(attempt)
                    logger.info(
                        "Retrying Shippo request correlation_id=%s method=%s "
                        "endpoint=%s category=timeout attempt=%d/%d delay_seconds=%.2f",
                        correlation_id,
                        method,
                        normalized_endpoint,
                        attempt + 1,
                        self.settings.max_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                self._log_terminal_request(
                    correlation_id, method, normalized_endpoint, attempt,
                    started_at, "timeout",
                )
                if method == "GET" and attempt == self.settings.max_attempts:
                    logger.warning(
                        "Shippo retries exhausted correlation_id=%s method=%s "
                        "endpoint=%s category=timeout attempts=%d",
                        correlation_id,
                        method,
                        normalized_endpoint,
                        attempt,
                    )
                raise ShippoTimeoutError("Shippo request timed out.") from exc
            except requests.RequestException as exc:
                # Only explicitly transient GET transport categories are replayed.
                can_retry = (
                    method == "GET"
                    and isinstance(exc, GET_RETRYABLE_EXCEPTIONS)
                    and attempt < self.settings.max_attempts
                )
                if can_retry:
                    delay = self._backoff_delay(attempt)
                    logger.info(
                        "Retrying Shippo request correlation_id=%s method=%s "
                        "endpoint=%s category=connection attempt=%d/%d "
                        "delay_seconds=%.2f",
                        correlation_id,
                        method,
                        normalized_endpoint,
                        attempt + 1,
                        self.settings.max_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                self._log_terminal_request(
                    correlation_id, method, normalized_endpoint, attempt,
                    started_at, "network_failure",
                )
                if (
                    method == "GET"
                    and isinstance(exc, GET_RETRYABLE_EXCEPTIONS)
                    and attempt == self.settings.max_attempts
                ):
                    logger.warning(
                        "Shippo retries exhausted correlation_id=%s method=%s "
                        "endpoint=%s category=connection attempts=%d",
                        correlation_id,
                        method,
                        normalized_endpoint,
                        attempt,
                    )
                raise ShippoAPIError("Unable to communicate with Shippo.") from exc

            if not response.ok:
                # Status retryability depends on method safety and remaining attempts.
                can_retry = (
                    self._is_retryable_status(method, response.status_code)
                    and attempt < self.settings.max_attempts
                )
                if can_retry:
                    # Retry-After is most relevant to 429 but is safe to honor on
                    # any explicitly retryable response returned by Shippo.
                    retry_after = response.headers.get("Retry-After")
                    delay = self._retry_after_delay(
                        retry_after,
                        self._backoff_delay(attempt),
                        correlation_id,
                    )
                    logger.info(
                        "Retrying Shippo request correlation_id=%s method=%s "
                        "endpoint=%s status=%d attempt=%d/%d delay_seconds=%.2f",
                        correlation_id,
                        method,
                        normalized_endpoint,
                        response.status_code,
                        attempt + 1,
                        self.settings.max_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                self._log_terminal_request(
                    correlation_id, method, normalized_endpoint, attempt,
                    started_at, f"http_{response.status_code}",
                )
                if (
                    self._is_retryable_status(method, response.status_code)
                    and attempt == self.settings.max_attempts
                ):
                    logger.warning(
                        "Shippo retries exhausted correlation_id=%s method=%s "
                        "endpoint=%s status=%d attempts=%d",
                        correlation_id,
                        method,
                        normalized_endpoint,
                        response.status_code,
                        attempt,
                    )
                raise ShippoAPIError(
                    f"Shippo returned HTTP {response.status_code}."
                )

            try:
                result = response.json()
            except ValueError as exc:
                # A successful POST may already be committed, so response parsing
                # failures are intentionally never retried.
                self._log_terminal_request(
                    correlation_id, method, normalized_endpoint, attempt,
                    started_at, "invalid_json",
                )
                raise ShippoResponseError("Shippo returned invalid JSON.") from exc

            if not isinstance(result, dict):
                self._log_terminal_request(
                    correlation_id, method, normalized_endpoint, attempt,
                    started_at, "non_object_json",
                )
                raise ShippoResponseError(
                    "Shippo returned a non-object JSON response."
                )

            self._log_terminal_request(
                correlation_id, method, normalized_endpoint, attempt,
                started_at, f"http_{response.status_code}",
            )
            return result

        raise ShippoAPIError("Shippo request attempts were exhausted.")

    def post(
        self,
        endpoint: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """POST JSON and return a decoded object response.

        POST retries only explicit HTTP 429 responses to minimize duplicate
        address or shipment creation after ambiguous transport failures.
        """
        return self._request(
            "POST",
            endpoint,
            payload,
            correlation_id=correlation_id,
        )

    def get(
        self,
        endpoint: str,
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """GET a Shippo resource with transient retries and return its object."""
        return self._request("GET", endpoint, correlation_id=correlation_id)