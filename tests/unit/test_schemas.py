"""Unit tests for Shippo integration Pydantic contracts."""

import unittest

from pydantic import ValidationError

from shippo_integration.schemas.error import BusinessErrorSchema
from shippo_integration.schemas import (
    AddressSchema,
    AddressValidationResult,
    ParcelSchema,
    ShippingErrorResult,
    ShippingQuoteRequestSchema,
    ShippingQuoteResult,
)


class ShippoSchemaTests(unittest.TestCase):
    """Verify schema validation without changing provider-compatible structures."""

    def test_partial_objects_and_provider_extensions_round_trip(self):
        """Preserve provider extensions after required shipping fields validate."""
        origin = {
            "name": "Warehouse",
            "street1": "1 Main Street",
            "city": "Origin City",
            "state": "CA",
            "zip": "90001",
            "country": "US",
            "metadata": {"source": "unit"},
        }
        destination = {
            "name": "Customer",
            "street1": "2 Oak Street",
            "city": "Destination City",
            "state": "GA",
            "zip": "30301",
            "country": "US",
        }
        request = ShippingQuoteRequestSchema.model_validate(
            {
                "address_from": origin,
                "address_to": destination,
                "parcels": [
                    {
                        "length": "24",
                        "width": "16",
                        "height": "12",
                        "distance_unit": "in",
                        "weight": "12",
                        "mass_unit": "lb",
                        "object_id": "parcel-1",
                    }
                ],
            }
        )

        payload = request.model_dump(
            by_alias=True,
            exclude_unset=True,
            exclude_none=True,
        )

        # Aliases and provider extensions must survive aggregate validation.
        self.assertEqual(payload["address_from"]["metadata"], {"source": "unit"})
        self.assertEqual(payload["parcels"][0]["object_id"], "parcel-1")
        self.assertEqual(payload["parcels"][0]["weight"], "12")

    def test_generic_address_remains_partial_but_shipping_requires_complete_addresses(self):
        """Apply address completeness only when constructing a shipment request."""
        partial_address = AddressSchema(zip="30301")

        self.assertEqual(partial_address.zip, "30301")
        with self.assertRaises(ValidationError) as context:
            ShippingQuoteRequestSchema(
                address_from=partial_address,
                address_to=partial_address,
                parcels=[ParcelSchema(
                    length="24",
                    width="16",
                    height="12",
                    distance_unit="in",
                    weight="12",
                    mass_unit="lb",
                )],
            )

        self.assertIn("address_from.name", str(context.exception))
        self.assertIn("address_to.street1", str(context.exception))

    def test_shipping_hardcodes_us_and_rejects_international_addresses(self):
        """Make country a US-only application rule instead of caller input."""
        address = {
            "name": "Name",
            "street1": "1 Main Street",
            "city": "City",
            "state": "CA",
            "zip": "90001",
        }
        request = ShippingQuoteRequestSchema(
            address_from=address,
            address_to=address,
            parcels=[ParcelSchema(
                length="24",
                width="16",
                height="12",
                distance_unit="in",
                weight="12",
                mass_unit="lb",
            )],
        )

        payload = request.model_dump(exclude_unset=True, exclude_none=True)

        self.assertEqual(payload["address_from"]["country"], "US")
        self.assertEqual(payload["address_to"]["country"], "US")
        with self.assertRaises(ValidationError):
            ShippingQuoteRequestSchema(
                address_from=address,
                address_to={**address, "country": "CA"},
                parcels=[ParcelSchema(
                    length="24",
                    width="16",
                    height="12",
                    distance_unit="in",
                    weight="12",
                    mass_unit="lb",
                )],
            )

    def test_shipment_rejects_incomplete_or_nonpositive_parcels(self):
        """Keep generic parcels permissive but require complete shipment parcels."""
        address = AddressSchema(
            name="Name",
            street1="1 Main Street",
            city="City",
            state="CA",
            zip="90001",
            country="US",
        )
        invalid_parcels = (
            ParcelSchema(weight="12", mass_unit="lb"),
            ParcelSchema(
                length="0",
                width="16",
                height="12",
                distance_unit="in",
                weight="12",
                mass_unit="lb",
            ),
        )
        for parcel in invalid_parcels:
            with self.subTest(parcel=parcel), self.assertRaises(ValidationError):
                ShippingQuoteRequestSchema(
                    address_from=address,
                    address_to=address,
                    parcels=[parcel],
                )

    def test_address_validate_alias_uses_shippo_key(self):
        """Expose Shippo's validate key without shadowing BaseModel methods."""
        address = AddressSchema(validate_address=True)

        payload = address.model_dump(by_alias=True, exclude_unset=True)

        self.assertEqual(payload, {"validate": True})

    def test_request_requires_at_least_one_parcel(self):
        """Reject a quote request that cannot produce a shipment."""
        complete_address = AddressSchema(
            name="Name",
            street1="1 Main Street",
            city="City",
            state="CA",
            zip="90001",
            country="US",
        )
        with self.assertRaises(ValidationError):
            ShippingQuoteRequestSchema(
                address_from=complete_address,
                address_to=complete_address,
                parcels=[],
            )

    def test_response_dump_preserves_success_and_failure_key_sets(self):
        """Omit fields that do not belong to the selected result path."""
        success = ShippingQuoteResult(
            success=True,
            carrier="USPS",
            service="Priority",
            amount="12.00",
            currency="USD",
            estimated_days=None,
        ).model_dump(exclude_unset=True)
        failure = ShippingErrorResult(
            success=False,
            error_code="NO_RATES",
            message="No shipping rates available.",
            shippo_messages=[],
        ).model_dump(exclude_unset=True)

        self.assertEqual(
            set(success),
            {
                "success",
                "carrier",
                "service",
                "amount",
                "currency",
                "estimated_days",
            },
        )
        self.assertEqual(
            set(failure),
            {"success", "error_code", "message", "shippo_messages"},
        )

    def test_response_message_defaults_are_independent(self):
        """Prevent message mutations from leaking between response instances."""
        first = ShippingErrorResult(
            success=False, error_code="NO_RATES", message="No rates"
        )
        second = ShippingErrorResult(
            success=False, error_code="NO_RATES", message="No rates"
        )

        first.shippo_messages.append({"source": "Shippo", "message": "Unavailable"})

        # default_factory must isolate mutable message collections per result.
        self.assertEqual(second.shippo_messages, [])

    def test_all_supported_business_error_codes_validate(self):
        """Accept every documented machine-readable business error code."""
        supported_codes = (
            "NO_RATES",
            "INVALID_ADDRESS",
            "SHIPPO_TIMEOUT",
            "SHIPPO_FAILURE",
            "CONFIGURATION_ERROR",
        )

        for error_code in supported_codes:
            with self.subTest(error_code=error_code):
                result = BusinessErrorSchema(
                    error_code=error_code,
                    message="Failure",
                ).model_dump()
                self.assertEqual(result["error_code"], error_code)
                self.assertFalse(result["success"])

    def test_unsupported_business_error_code_is_rejected(self):
        """Reject undocumented codes that callers cannot handle reliably."""
        with self.assertRaises(ValidationError):
            BusinessErrorSchema(error_code="UNKNOWN", message="Failure")

    def test_quote_failure_includes_error_code_without_changing_success(self):
        """Use distinct literal-discriminated shipping result models."""
        failure = ShippingErrorResult(
            success=False,
            error_code="NO_RATES",
            message="No rates",
            shippo_messages=[],
        ).model_dump(exclude_unset=True)
        success = ShippingQuoteResult(
            success=True,
            carrier="USPS",
            service="Priority",
            amount="12.00",
            currency="USD",
            estimated_days=None,
        ).model_dump(exclude_unset=True)

        self.assertEqual(failure["error_code"], "NO_RATES")
        self.assertNotIn("error_code", success)
        self.assertNotIn("message", success)

    def test_shipping_result_models_reject_wrong_success_discriminator(self):
        """Prevent success fields and error fields from sharing one ambiguous model."""
        with self.assertRaises(ValidationError):
            ShippingQuoteResult(
                success=False,
                carrier="USPS",
                service="Priority",
                amount="12.00",
                currency="USD",
                estimated_days=None,
            )
        with self.assertRaises(ValidationError):
            ShippingErrorResult(
                success=True,
                error_code="NO_RATES",
                message="No rates",
            )

    def test_address_validation_result_serializes_legacy_fields(self):
        """Keep established address fields in the typed result wire shape."""
        result = AddressValidationResult(
            success=False,
            valid=False,
            zip=None,
            is_residential=None,
            messages=[],
            error_code="INVALID_ADDRESS",
            message="Invalid address",
        )

        self.assertEqual(result.error_code, "INVALID_ADDRESS")
        self.assertEqual(
            result.model_dump(exclude_unset=True),
            {
                "success": False,
                "valid": False,
                "zip": None,
                "is_residential": None,
                "messages": [],
                "error_code": "INVALID_ADDRESS",
                "message": "Invalid address",
            },
        )

    def test_parcel_schema_accepts_existing_numeric_representations(self):
        """Keep numeric values numeric when callers do not provide strings."""
        parcel = ParcelSchema(length=24, width=16.5, weight="12")

        payload = parcel.model_dump(exclude_unset=True)

        self.assertEqual(payload, {"length": 24, "width": 16.5, "weight": "12"})


if __name__ == "__main__":
    unittest.main()