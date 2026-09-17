"""Unit tests for Shippo HTTP transport and exception translation."""

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import UUID

import requests

from shippo_integration.client import ShippoClient
from shippo_integration.config import ShippoSettings
from shippo_integration.exceptions import (
    ShippoAPIError,
    ShippoResponseError,
    ShippoTimeoutError,
)


class ShippoClientTests(unittest.TestCase):
    """Exercise client behavior entirely through mocked HTTP responses."""

    def setUp(self):
        """Create deterministic settings with no dependency on the real dotenv file."""
        self.client = ShippoClient(ShippoSettings("sentinel-key", "https://test", 5))

    @staticmethod
    def successful_response(payload=None):
        """Build a successful mocked response containing an object JSON body."""
        response = Mock(ok=True, status_code=200, headers={})
        response.json.return_value = payload or {"object_id": "shipment-1"}
        return response

    @patch(
        "shippo_integration.client.uuid.uuid4",
        return_value=UUID("12345678-1234-1234-1234-123456789abc"),
    )
    @patch("shippo_integration.client.requests.request")
    def test_post_uses_normalized_url_body_and_correlation_id(self, request, _uuid):
        """Send POST data with configured authentication and timeout."""
        request.return_value = self.successful_response()

        result = self.client.post("/shipments/", {"parcel": 1})

        self.assertEqual(result, {"object_id": "shipment-1"})
        request.assert_called_once_with(
            "POST",
            "https://test/shipments/",
            json={"parcel": 1},
            headers={
                **self.client.headers,
                "X-Correlation-ID": "12345678-1234-1234-1234-123456789abc",
            },
            timeout=5,
        )

    @patch("shippo_integration.client.uuid.uuid4")
    @patch("shippo_integration.client.requests.request")
    def test_supplied_correlation_id_bypasses_uuid_generation(self, request, uuid4):
        """Use an HTTP caller's identifier unchanged in the Shippo header."""
        request.return_value = self.successful_response()

        self.client.post("/shipments/", {}, correlation_id="caller-correlation")

        self.assertEqual(
            request.call_args.kwargs["headers"]["X-Correlation-ID"],
            "caller-correlation",
        )
        uuid4.assert_not_called()

    @patch("shippo_integration.client.time.sleep")
    @patch("shippo_integration.client.requests.request")
    def test_get_retries_timeout_then_succeeds(self, request, sleep):
        """Retry a transient GET timeout with exponential backoff."""
        request.side_effect = [requests.Timeout(), self.successful_response()]

        result = self.client.get("/carrier_accounts/")

        self.assertEqual(result, {"object_id": "shipment-1"})
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(0.5)

    @patch("shippo_integration.client.time.sleep")
    @patch("shippo_integration.client.requests.request")
    def test_get_uses_exponential_backoff_for_gateway_failures(self, request, sleep):
        """Retry GET gateway failures with 0.5 and 1.0 second fallback delays."""
        # Consecutive failures expose both first and second exponential delays.
        request.side_effect = [
            Mock(ok=False, status_code=503, headers={}),
            Mock(ok=False, status_code=504, headers={}),
            self.successful_response(),
        ]

        self.client.get("/carrier_accounts/")

        self.assertEqual(request.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])

    def test_get_recovers_from_each_transient_category(self):
        """Retry connection/chunk failures and every documented transient status."""
        transient_outcomes = (
            requests.ConnectionError(),
            requests.exceptions.ChunkedEncodingError(),
            Mock(ok=False, status_code=429, headers={}),
            Mock(ok=False, status_code=502, headers={}),
            Mock(ok=False, status_code=503, headers={}),
            Mock(ok=False, status_code=504, headers={}),
        )

        for outcome in transient_outcomes:
            with self.subTest(outcome=type(outcome).__name__), patch(
                "shippo_integration.client.requests.request",
                side_effect=[outcome, self.successful_response()],
            ) as request, patch("shippo_integration.client.time.sleep") as sleep:
                result = self.client.get("/carrier_accounts/")
                self.assertEqual(result, {"object_id": "shipment-1"})
                self.assertEqual(request.call_count, 2)
                sleep.assert_called_once_with(0.5)

    @patch("shippo_integration.client.time.sleep")
    @patch("shippo_integration.client.requests.request")
    def test_get_exhausted_timeout_preserves_exception(self, request, sleep):
        """Raise ShippoTimeoutError after all GET timeout attempts fail."""
        request.side_effect = requests.Timeout()

        with self.assertRaises(ShippoTimeoutError):
            self.client.get("/carrier_accounts/")

        self.assertEqual(request.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("shippo_integration.client.time.sleep")
    @patch("shippo_integration.client.requests.request")
    def test_post_retries_only_rate_limit_and_reuses_correlation_id(
        self, request, sleep
    ):
        """Retry POST 429 responses while retaining one request identifier."""
        request.side_effect = [
            Mock(ok=False, status_code=429, headers={"Retry-After": "120"}),
            self.successful_response(),
        ]

        result = self.client.post("/shipments/", {"parcel": 1})

        self.assertEqual(result, {"object_id": "shipment-1"})
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(30.0)
        # One logical request must retain one trace identifier across retries.
        correlation_ids = {
            call.kwargs["headers"]["X-Correlation-ID"]
            for call in request.call_args_list
        }
        self.assertEqual(len(correlation_ids), 1)

    @patch("shippo_integration.client.time.sleep")
    @patch("shippo_integration.client.requests.request")
    def test_post_rate_limit_stops_after_max_attempts(self, request, sleep):
        """Raise ShippoAPIError after the configured number of POST 429 responses."""
        request.return_value = Mock(ok=False, status_code=429, headers={})

        with self.assertRaisesRegex(ShippoAPIError, "HTTP 429"):
            self.client.post("/shipments/", {"parcel": 1})

        self.assertEqual(request.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])

    def test_post_does_not_retry_ambiguous_failures(self):
        """Avoid duplicate POST operations after transport or gateway ambiguity."""
        cases = (
            (requests.Timeout(), ShippoTimeoutError),
            (requests.ConnectionError(), ShippoAPIError),
            (Mock(ok=False, status_code=502, headers={}), ShippoAPIError),
            (Mock(ok=False, status_code=503, headers={}), ShippoAPIError),
            (Mock(ok=False, status_code=504, headers={}), ShippoAPIError),
        )

        for outcome, expected_error in cases:
            with self.subTest(outcome=type(outcome).__name__), patch(
                "shippo_integration.client.requests.request", side_effect=[outcome]
            ) as request, patch("shippo_integration.client.time.sleep") as sleep:
                with self.assertRaises(expected_error):
                    self.client.post("/shipments/", {"parcel": 1})
                self.assertEqual(request.call_count, 1)
                sleep.assert_not_called()

    @patch("shippo_integration.client.requests.request")
    def test_rejects_http_failure(self, request):
        """Translate unsuccessful status codes into ShippoAPIError."""
        request.return_value = Mock(ok=False, status_code=401)
        with self.assertRaises(ShippoAPIError):
            self.client.get("/carrier_accounts/")
        self.assertEqual(request.call_count, 1)

    @patch("shippo_integration.client.requests.request")
    def test_rejects_non_object_json(self, request):
        """Reject valid JSON values that violate the expected object contract."""
        response = Mock(ok=True, status_code=200)
        response.json.return_value = []
        request.return_value = response
        with self.assertRaises(ShippoResponseError):
            self.client.get("/carrier_accounts/")
        self.assertEqual(request.call_count, 1)

    @patch("shippo_integration.client.time.sleep")
    @patch("shippo_integration.client.requests.request")
    def test_malformed_retry_after_falls_back_and_warns(self, request, sleep):
        """Use exponential backoff when a rate-limit header cannot be parsed."""
        # An invalid provider header must not bypass the bounded fallback policy.
        request.side_effect = [
            Mock(ok=False, status_code=429, headers={"Retry-After": "invalid"}),
            self.successful_response(),
        ]

        with self.assertLogs("shippo_integration.client", level="WARNING") as logs:
            self.client.get("/carrier_accounts/")

        sleep.assert_called_once_with(0.5)
        self.assertIn("Malformed Retry-After", " ".join(logs.output))

    def test_http_date_retry_after_is_capped(self):
        """Parse an HTTP-date Retry-After value and enforce the configured cap."""
        future = "Wed, 01 Jan 2031 00:01:00 GMT"
        fixed_now = datetime(2031, 1, 1, tzinfo=timezone.utc)
        with patch("shippo_integration.client.datetime") as date_time:
            # Freeze wall-clock time so the HTTP-date delta is deterministic.
            date_time.now.return_value = fixed_now
            delay = self.client._retry_after_delay(future, 0.5, "correlation")

        self.assertEqual(delay, 30.0)

    @patch("shippo_integration.client.time.perf_counter", side_effect=[10.0, 10.125])
    @patch("shippo_integration.client.requests.request")
    def test_logs_latency_without_secrets_or_payload(self, request, _timer):
        """Log correlation and latency while excluding credentials and body data."""
        request.return_value = self.successful_response()

        with self.assertLogs("shippo_integration.client", level="DEBUG") as logs:
            self.client.post("/shipments/?secret=query", {"private": "payload"})

        output = " ".join(logs.output)
        # Operational metadata is useful; secrets, bodies, and queries are not.
        self.assertIn("latency_ms=125.00", output)
        self.assertIn("correlation_id=", output)
        self.assertIn("endpoint=/shipments/", output)
        self.assertNotIn("sentinel-key", output)
        self.assertNotIn("ShippoToken", output)
        self.assertNotIn("private", output)
        self.assertNotIn("secret=query", output)


if __name__ == "__main__":
    unittest.main()