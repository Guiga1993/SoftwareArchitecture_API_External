"""HTTP-level tests for the local Shippo integration service."""

import unittest
from unittest.mock import patch

import app as api
from shippo_integration.schemas import (
    AddressValidationResult,
    ShippingErrorResult,
    ShippingQuoteResult,
)


class IntegrationAPIEndpointTests(unittest.TestCase):
    """Verify thin route adaptation, error mapping, and request correlation."""

    def setUp(self):
        """Create an in-process client and valid endpoint request bodies."""
        self.client = api.app.test_client()
        self.address_payload = {
            "customer_name": "Customer Company",
            "street1": "123 Main Street",
            "city": "Atlanta",
            "state": "GA",
            "zip_code": "30301",
            "country": "US",
        }
        self.quote_payload = {
            "address_from": {
                "name": "Origin Company",
                "street1": "1 Main Street",
                "city": "Torrance",
                "state": "CA",
                "zip": "90504",
                "country": "US",
            },
            "address_to": {
                "name": "Customer Company",
                "street1": "123 Main Street",
                "city": "Atlanta",
                "state": "GA",
                "zip": "30301",
                "country": "US",
            },
            "parcels": [
                {
                    "length": "48",
                    "width": "40",
                    "height": "60",
                    "distance_unit": "in",
                    "weight": "12",
                    "mass_unit": "lb",
                }
            ],
        }

    def test_health_is_liveness_only_and_echoes_correlation_id(self):
        """Return the exact health body without touching Shippo configuration."""
        # Patching every dependency proves liveness is independent of readiness.
        with patch("app.get_integration_api_settings") as settings, patch(
            "app.validate_address"
        ) as address_service, patch("app.get_shipping_quote") as quote_service:
            response = self.client.get(
                "/health",
                headers={"X-Correlation-ID": "caller-health-id"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "up", "service": "shippo-integration"},
        )
        self.assertEqual(response.headers["X-Correlation-ID"], "caller-health-id")
        settings.assert_not_called()
        address_service.assert_not_called()
        quote_service.assert_not_called()

    def test_root_and_openapi_are_available(self):
        """Redirect root to documentation and publish all Phase A routes."""
        root = self.client.get("/")
        docs = self.client.get("/openapi", follow_redirects=True)
        spec = self.client.get("/openapi/openapi.json")

        self.assertEqual(root.status_code, 302)
        self.assertTrue(root.headers["Location"].endswith("/openapi"))
        self.assertEqual(docs.status_code, 200)
        self.assertEqual(spec.status_code, 200)
        # OpenAPI may add framework paths; these application routes must remain.
        self.assertTrue(
            {"/health", "/validate-address", "/shipping-quote"}
            <= set(spec.get_json()["paths"])
        )

    @patch("app.validate_address")
    def test_valid_address_returns_200_and_forwards_correlation(self, service):
        """Adapt the internal zip field and preserve request tracing."""
        service.return_value = AddressValidationResult(
            success=True,
            valid=True,
            zip="30301-1234",
            is_residential=True,
            messages=[],
        )

        response = self.client.post(
            "/validate-address",
            json=self.address_payload,
            headers={"X-Correlation-ID": "address-correlation"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "success": True,
                "valid": True,
                "normalized_zip": "30301-1234",
                "is_residential": True,
                "messages": [],
            },
        )
        self.assertEqual(response.headers["X-Correlation-ID"], "address-correlation")
        service.assert_called_once_with(
            name="Customer Company",
            street1="123 Main Street",
            city="Atlanta",
            state="GA",
            zip_code="30301",
            country="US",
            correlation_id="address-correlation",
        )

    @patch("app.validate_address")
    def test_invalid_address_remains_http_200(self, service):
        """Treat INVALID_ADDRESS as a completed business result."""
        service.return_value = AddressValidationResult(
            success=False,
            valid=False,
            zip=None,
            is_residential=None,
            messages=[{"text": "Invalid"}],
            error_code="INVALID_ADDRESS",
            message="Shippo could not validate the supplied address.",
        )

        response = self.client.post("/validate-address", json=self.address_payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["error_code"], "INVALID_ADDRESS")

    def test_address_business_failures_map_to_http_statuses(self):
        """Map typed address technical failures without handling adapter exceptions."""
        # The route maps stable service codes rather than provider exception types.
        cases = (
            ("CONFIGURATION_ERROR", 503),
            ("SHIPPO_TIMEOUT", 504),
            ("SHIPPO_FAILURE", 502),
        )
        for error_code, status in cases:
            with self.subTest(error_code=error_code), patch(
                "app.validate_address",
                return_value=AddressValidationResult(
                    success=False,
                    valid=False,
                    zip=None,
                    is_residential=None,
                    messages=[],
                    error_code=error_code,
                    message="Safe failure",
                ),
            ):
                response = self.client.post(
                    "/validate-address", json=self.address_payload
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.get_json()["message"], "Safe failure")

    @patch("app.get_shipping_quote")
    def test_successful_quote_returns_200_and_forwards_correlation(self, service):
        """Adapt a typed quote and forward both caller-owned addresses."""
        service.return_value = ShippingQuoteResult(
            success=True,
            carrier="USPS",
            service="Priority",
            amount="12.00",
            currency="USD",
            estimated_days=3,
        )

        response = self.client.post(
            "/shipping-quote",
            json=self.quote_payload,
            headers={"X-Correlation-ID": "quote-correlation"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["carrier"], "USPS")
        self.assertEqual(response.headers["X-Correlation-ID"], "quote-correlation")
        call = service.call_args
        self.assertEqual(call.kwargs["address_from"]["zip"], "90504")
        self.assertEqual(call.kwargs["correlation_id"], "quote-correlation")
        self.assertEqual(call.kwargs["address_to"]["country"], "US")

    def test_shipping_business_failures_map_to_http_statuses(self):
        """Keep NO_RATES at 200 and map technical business codes centrally."""
        # NO_RATES is completed business processing; technical failures are 5xx.
        cases = (
            ("NO_RATES", 200),
            ("CONFIGURATION_ERROR", 503),
            ("SHIPPO_TIMEOUT", 504),
            ("SHIPPO_FAILURE", 502),
        )
        for error_code, status in cases:
            with self.subTest(error_code=error_code), patch(
                "app.get_shipping_quote",
                return_value=ShippingErrorResult(
                    success=False,
                    error_code=error_code,
                    message="Safe failure",
                    shippo_messages=[],
                ),
            ):
                response = self.client.post(
                    "/shipping-quote", json=self.quote_payload
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.get_json()["error_code"], error_code)

    def test_unexpected_route_defects_return_safe_500(self):
        """Hide raw exception text while preserving HTTP process stability."""
        for route, service_name, payload in (
            ("/validate-address", "app.validate_address", self.address_payload),
            ("/shipping-quote", "app.get_shipping_quote", self.quote_payload),
        ):
            with self.subTest(route=route), patch(
                service_name, side_effect=RuntimeError("raw secret detail")
            ):
                response = self.client.post(route, json=payload)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn("raw secret detail", response.get_data(as_text=True))
                self.assertEqual(response.get_json()["error_code"], "SHIPPO_FAILURE")

    def test_malformed_and_non_json_requests_are_rejected(self):
        """Use framework validation for malformed JSON and 415 for wrong media type."""
        malformed_address = {**self.address_payload}
        malformed_address.pop("street1")
        malformed_quote = {**self.quote_payload}
        malformed_quote.pop("address_from")

        # Boundary rejection must occur before either business service executes.
        with patch("app.validate_address") as address_service:
            malformed = self.client.post(
                "/validate-address", json=malformed_address
            )
            wrong_media = self.client.post(
                "/validate-address", data="text", content_type="text/plain"
            )
        with patch("app.get_shipping_quote") as quote_service:
            missing_origin = self.client.post(
                "/shipping-quote", json=malformed_quote
            )
            quote_wrong_media = self.client.post(
                "/shipping-quote", data="text", content_type="text/plain"
            )

        self.assertEqual(malformed.status_code, 422)
        self.assertEqual(wrong_media.status_code, 415)
        self.assertEqual(missing_origin.status_code, 422)
        self.assertEqual(quote_wrong_media.status_code, 415)
        self.assertTrue(malformed.headers.get("X-Correlation-ID"))
        self.assertTrue(wrong_media.headers.get("X-Correlation-ID"))
        self.assertTrue(quote_wrong_media.headers.get("X-Correlation-ID"))
        address_service.assert_not_called()
        quote_service.assert_not_called()

    def test_shipping_rejects_invalid_addresses_and_parcels(self):
        """Reject international addresses and nonpositive parcel measurements."""
        origin_without_street = dict(self.quote_payload["address_from"])
        origin_without_street.pop("street1")
        destination_without_city = dict(self.quote_payload["address_to"])
        destination_without_city.pop("city")
        # Each payload violates one independent HTTP-boundary contract.
        cases = (
            {**self.quote_payload, "address_from": origin_without_street},
            {**self.quote_payload, "address_to": destination_without_city},
            {**self.quote_payload, "address_from": {**self.quote_payload["address_from"], "country": "CA"}},
            {**self.quote_payload, "address_to": {**self.quote_payload["address_to"], "state": "G"}},
            {**self.quote_payload, "parcels": []},
            {**self.quote_payload, "parcels": [{**self.quote_payload["parcels"][0], "weight": "0"}]},
            {**self.quote_payload, "parcels": [{**self.quote_payload["parcels"][0], "length": "-1"}]},
        )
        for payload in cases:
            with self.subTest(payload=payload), patch("app.get_shipping_quote") as service:
                response = self.client.post("/shipping-quote", json=payload)
                self.assertEqual(response.status_code, 422)
                service.assert_not_called()


if __name__ == "__main__":
    unittest.main()