"""Unit tests for Shippo environment configuration."""

import os
import unittest
from unittest.mock import patch

from shippo_integration.config import (
    get_integration_api_settings,
    ShippoSettings,
    get_shippo_settings,
)
from shippo_integration.exceptions import ShippoConfigurationError


class ShippoConfigurationTests(unittest.TestCase):
    """Verify settings validation without exposing real credentials."""

    def test_process_environment_builds_settings(self):
        """Use explicit process values for connection and retry settings."""
        environment = {
            "SHIPPO_API_KEY": "sentinel-key",
            "SHIPPO_BASE_URL": "https://example.test/",
            "SHIPPO_TIMEOUT_SECONDS": "15",
            "SHIPPO_MAX_ATTEMPTS": "4",
            "SHIPPO_BACKOFF_SECONDS": "0.25",
            "SHIPPO_MAX_RETRY_AFTER_SECONDS": "10",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = get_shippo_settings()

        self.assertEqual(settings.api_key, "sentinel-key")
        self.assertEqual(settings.base_url, "https://example.test")
        self.assertEqual(settings.timeout_seconds, 15.0)
        self.assertEqual(settings.max_attempts, 4)
        self.assertEqual(settings.backoff_seconds, 0.25)
        self.assertEqual(settings.max_retry_after_seconds, 10.0)

    def test_legacy_settings_construction_uses_safe_retry_defaults(self):
        """Preserve three-argument settings construction with conservative defaults."""
        settings = ShippoSettings("sentinel-key", "https://example.test", 15)

        self.assertEqual(settings.max_attempts, 3)
        self.assertEqual(settings.backoff_seconds, 0.5)
        self.assertEqual(settings.max_retry_after_seconds, 30.0)

    @patch("shippo_integration.config.load_shippo_environment")
    def test_http_server_settings_defaults_and_overrides(self, _load_environment):
        """Load local server defaults and accepted explicit environment values."""
        with patch.dict(os.environ, {}, clear=True):
            defaults = get_integration_api_settings()
        self.assertEqual((defaults.host, defaults.port, defaults.debug), ("127.0.0.1", 8001, False))

        environment = {
            "INTEGRATION_API_HOST": "0.0.0.0",
            "INTEGRATION_API_PORT": "9001",
            "INTEGRATION_API_DEBUG": "on",
        }
        with patch.dict(os.environ, environment, clear=True):
            configured = get_integration_api_settings()
        self.assertEqual((configured.host, configured.port, configured.debug), ("0.0.0.0", 9001, True))

    @patch("shippo_integration.config.load_shippo_environment")
    def test_rejects_invalid_http_server_settings(self, _load_environment):
        """Reject invalid local HTTP port and debug values."""
        # Cover numeric bounds, parsing, and accepted-boolean vocabulary.
        for environment in (
            {"INTEGRATION_API_PORT": "0"},
            {"INTEGRATION_API_PORT": "not-a-port"},
            {"INTEGRATION_API_DEBUG": "maybe"},
        ):
            with self.subTest(environment=environment), patch.dict(
                os.environ, environment, clear=True
            ):
                with self.assertRaises(ShippoConfigurationError):
                    get_integration_api_settings()

    def test_rejects_invalid_timeout(self):
        """Reject non-positive request timeouts before client construction."""
        with patch.dict(
            os.environ,
            {"SHIPPO_API_KEY": "sentinel-key", "SHIPPO_TIMEOUT_SECONDS": "0"},
            clear=True,
        ):
            with self.assertRaises(ShippoConfigurationError):
                get_shippo_settings()

    @patch("shippo_integration.config.load_shippo_environment")
    def test_rejects_invalid_retry_settings(self, _load_environment):
        """Reject invalid attempt, backoff, and Retry-After cap values."""
        # Each field has a distinct lower-bound or numeric parsing contract.
        invalid_settings = (
            {"SHIPPO_MAX_ATTEMPTS": "0"},
            {"SHIPPO_MAX_ATTEMPTS": "not-an-integer"},
            {"SHIPPO_BACKOFF_SECONDS": "-1"},
            {"SHIPPO_MAX_RETRY_AFTER_SECONDS": "0"},
        )

        for invalid_setting in invalid_settings:
            environment = {"SHIPPO_API_KEY": "sentinel-key", **invalid_setting}
            with self.subTest(invalid_setting=invalid_setting), patch.dict(
                os.environ, environment, clear=True
            ):
                with self.assertRaises(ShippoConfigurationError):
                    get_shippo_settings()

if __name__ == "__main__":
    unittest.main()