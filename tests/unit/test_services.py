"""Unit tests for generic address and shipping operations."""

import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from shippo_integration.exceptions import (
    ShippoAPIError,
    ShippoConfigurationError,
    ShippoResponseError,
    ShippoTimeoutError,
)
from shippo_integration.schemas import (
    AddressSchema,
    AddressValidationResult,
    ParcelSchema,
    ShippingErrorResult,
    ShippingQuoteResult,
)
from shippo_integration.services import get_shipping_quote, validate_address


class ShippoServiceTests(unittest.TestCase):
    """Verify service payloads and response simplification with injected clients."""

    def setUp(self):
        """Provide deterministic caller-owned addresses for shipping tests."""
        self.origin = {
            "name": "Origin Company",
            "street1": "1 Main Street",
            "city": "Torrance",
            "state": "CA",
            "zip": "90504",
            "country": "US",
        }
        self.destination = {
            "name": "Customer",
            "street1": "2 Oak Street",
            "city": "Destination City",
            "state": "GA",
            "zip": "30301",
            "country": "US",
        }
        self.parcel = {
            "length": "24",
            "width": "16",
            "height": "12",
            "distance_unit": "in",
            "weight": "12",
            "mass_unit": "lb",
        }
    def test_address_validation_builds_payload(self):
        """Map Shippo validation data to the stable address result."""
        client = Mock()
        client.post.return_value = {
            "zip": "94117-1234",
            "is_residential": True,
            "validation_results": {"is_valid": True, "messages": []},
        }

        result = validate_address(
            "John Doe", "215 Clayton Street", "San Francisco", "CA", "94117",
            client=client,
        )

        self.assertIsInstance(result, AddressValidationResult)
        self.assertTrue(result.valid)
        self.assertTrue(result.success)
        self.assertEqual(result.zip, "94117-1234")
        self.assertEqual(
            client.post.call_args.args,
            (
                "/addresses/",
                {
                    "name": "John Doe",
                    "street1": "215 Clayton Street",
                    "city": "San Francisco",
                    "state": "CA",
                    "zip": "94117",
                    "country": "US",
                    "validate": True,
                },
            ),
        )

    def test_shipping_selects_cheapest_rate(self):
        """Return the lowest numeric amount from available Shippo rates."""
        client = Mock()
        client.post.return_value = {
            "rates": [
                {"provider": "UPS", "servicelevel": {"name": "Ground"}, "amount": "20.00"},
                {"provider": "USPS", "servicelevel": {"name": "Priority"}, "amount": "12.00"},
            ]
        }

        result = get_shipping_quote(
            self.origin,
            self.destination,
            [self.parcel],
            client=client,
        )

        self.assertIsInstance(result, ShippingQuoteResult)
        self.assertTrue(result.success)
        self.assertEqual(result.carrier, "USPS")
        self.assertEqual(result.amount, "12.00")
        self.assertEqual(
            client.post.call_args.args,
            (
                "/shipments/",
                {
                    "address_from": {
                        "name": "Origin Company",
                        "street1": "1 Main Street",
                        "city": "Torrance",
                        "state": "CA",
                        "zip": "90504",
                        "country": "US",
                    },
                    "address_to": self.destination,
                    "parcels": [self.parcel],
                },
            ),
        )
        self.assertEqual(
            set(result.model_dump(exclude_unset=True)),
            {
                "success",
                "carrier",
                "service",
                "amount",
                "currency",
                "estimated_days",
            },
        )

    def test_shipping_accepts_schema_instances(self):
        """Allow typed callers without removing dictionary compatibility."""
        client = Mock()
        # Empty rates exercise typed-input handling through the NO_RATES branch.
        client.post.return_value = {"rates": []}

        result = get_shipping_quote(
            AddressSchema(**self.origin),
            AddressSchema(**self.destination),
            [ParcelSchema(**self.parcel)],
            client=client,
        )

        self.assertIsInstance(result, ShippingErrorResult)
        self.assertEqual(
            result.model_dump(exclude_unset=True),
            {
                "success": False,
                "error_code": "NO_RATES",
                "message": "No shipping rates available.",
                "shippo_messages": [],
            },
        )

    def test_invalid_address_retains_legacy_fields_and_adds_error_code(self):
        """Return INVALID_ADDRESS without removing established address fields."""
        client = Mock()
        client.post.return_value = {
            "zip": "94117",
            "is_residential": None,
            "validation_results": {
                "is_valid": False,
                "messages": [{"text": "Street not found."}],
            },
        }

        result = validate_address(
            "John Doe", "Unknown", "San Francisco", "CA", "94117",
            client=client,
        )

        self.assertIsInstance(result, AddressValidationResult)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "INVALID_ADDRESS")
        self.assertIsNotNone(result.message)
        self.assertFalse(result.valid)
        self.assertEqual(result.zip, "94117")
        self.assertEqual(result.messages, [{"text": "Street not found."}])

    def test_no_rates_retains_legacy_shipping_fields(self):
        """Add NO_RATES while preserving message and shippo_messages."""
        client = Mock()
        # Shippo's ``text`` key is normalized to the public ``message`` key.
        client.post.return_value = {
            "rates": [],
            "messages": [{"source": "UPS", "text": "Unavailable"}],
        }

        result = get_shipping_quote(
            self.origin,
            self.destination,
            [self.parcel],
            client=client,
        )

        self.assertIsInstance(result, ShippingErrorResult)
        self.assertEqual(
            result.model_dump(exclude_unset=True),
            {
                "success": False,
                "error_code": "NO_RATES",
                "message": "No shipping rates available.",
                "shippo_messages": [
                    {"source": "UPS", "message": "Unavailable"}
                ],
            },
        )

    def test_malformed_rate_returns_shippo_failure(self):
        """Treat an unusable provider rate as a structured Shippo failure."""
        client = Mock()
        # The rate lacks the amount needed for cheapest-rate comparison.
        client.post.return_value = {"rates": [{"provider": "UPS"}]}

        result = get_shipping_quote(
            self.origin,
            self.destination,
            [self.parcel],
            client=client,
        )

        self.assertIsInstance(result, ShippingErrorResult)
        self.assertEqual(result.error_code, "SHIPPO_FAILURE")
        self.assertEqual(result.shippo_messages, [])

    def test_shipping_maps_adapter_exceptions_to_business_codes(self):
        """Convert configuration and transport failures to stable quote results."""
        # Preserve actionable categories while collapsing provider details safely.
        cases = (
            (ShippoConfigurationError(), "CONFIGURATION_ERROR"),
            (ShippoTimeoutError(), "SHIPPO_TIMEOUT"),
            (ShippoAPIError(), "SHIPPO_FAILURE"),
            (ShippoResponseError(), "SHIPPO_FAILURE"),
        )

        for error, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                client = Mock()
                client.post.side_effect = error
                result = get_shipping_quote(
                    self.origin,
                    self.destination,
                    [self.parcel],
                    client=client,
                )
                self.assertIsInstance(result, ShippingErrorResult)
                self.assertEqual(result.error_code, expected_code)
                self.assertEqual(result.shippo_messages, [])

    def test_address_maps_adapter_exceptions_to_business_codes(self):
        """Convert configuration and transport failures to stable address results."""
        cases = (
            (ShippoConfigurationError(), "CONFIGURATION_ERROR"),
            (ShippoTimeoutError(), "SHIPPO_TIMEOUT"),
            (ShippoAPIError(), "SHIPPO_FAILURE"),
            (ShippoResponseError(), "SHIPPO_FAILURE"),
        )

        for error, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                client = Mock()
                client.post.side_effect = error
                result = validate_address(
                    "John Doe", "Street", "City", "CA", "94117", client=client
                )
                self.assertIsInstance(result, AddressValidationResult)
                self.assertEqual(result.error_code, expected_code)
                self.assertFalse(result.valid)
                self.assertEqual(result.messages, [])

    def test_client_construction_configuration_failure_is_structured(self):
        """Map missing configuration even when failure occurs before an HTTP call."""
        with patch(
            "shippo_integration.services.address.ShippoClient",
            side_effect=ShippoConfigurationError(),
        ):
            result = validate_address("John Doe", "Street", "City", "CA", "94117")

        self.assertIsInstance(result, AddressValidationResult)
        self.assertEqual(result.error_code, "CONFIGURATION_ERROR")

        with patch(
            "shippo_integration.services.shipping.ShippoClient",
            side_effect=ShippoConfigurationError(),
        ):
            quote = get_shipping_quote(
                self.origin,
                self.destination,
                [self.parcel],
            )

        self.assertIsInstance(quote, ShippingErrorResult)
        self.assertEqual(quote.error_code, "CONFIGURATION_ERROR")

    def test_incomplete_destination_fails_before_shippo_call(self):
        """Expose caller validation errors instead of sending incomplete addresses."""
        client = Mock()

        with self.assertRaises(ValidationError):
            get_shipping_quote(self.origin, {"zip": "30301"}, [self.parcel], client=client)

        client.post.assert_not_called()

    def test_non_us_destination_fails_before_shippo_call(self):
        """Reject international destinations before constructing a shipment."""
        client = Mock()

        with self.assertRaises(ValidationError):
            get_shipping_quote(
                self.origin,
                {**self.destination, "country": "CA"},
                [self.parcel],
                client=client,
            )

        client.post.assert_not_called()

    def test_shipping_requires_a_parcel(self):
        """Reject empty shipments before constructing a Shippo client."""
        with self.assertRaises(ValueError):
            get_shipping_quote(self.origin, self.destination, [])

    def test_services_forward_supplied_correlation_ids(self):
        """Propagate one HTTP request identifier without changing payloads."""
        client = Mock()
        client.post.return_value = {
            "validation_results": {"is_valid": True, "messages": []}
        }
        validate_address(
            "Customer",
            "123 Main Street",
            "Atlanta",
            "GA",
            "30301",
            client=client,
            correlation_id="address-correlation",
        )
        self.assertEqual(
            client.post.call_args.kwargs["correlation_id"],
            "address-correlation",
        )

        client.reset_mock()
        client.post.return_value = {"rates": []}
        get_shipping_quote(
            self.origin,
            self.destination,
            [{"length": "1", "width": "1", "height": "1", "distance_unit": "in", "weight": "1", "mass_unit": "lb"}],
            client=client,
            correlation_id="quote-correlation",
        )
        self.assertEqual(
            client.post.call_args.kwargs["correlation_id"],
            "quote-correlation",
        )


if __name__ == "__main__":
    unittest.main()