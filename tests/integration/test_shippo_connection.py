"""Opt-in connectivity check for configured Shippo credentials."""

import os
import unittest

from shippo_integration import ShippoClient


@unittest.skipUnless(
    os.getenv("RUN_SHIPPO_INTEGRATION") == "1",
    "Set RUN_SHIPPO_INTEGRATION=1 to contact Shippo.",
)
class ShippoConnectionTests(unittest.TestCase):
    """Verify that explicitly enabled credentials can reach Shippo."""

    def test_lists_carrier_accounts(self):
        """Request carrier accounts and verify Shippo returns a JSON object."""
        response = ShippoClient().get("/carrier_accounts/")
        self.assertIsInstance(response, dict)


if __name__ == "__main__":
    unittest.main()