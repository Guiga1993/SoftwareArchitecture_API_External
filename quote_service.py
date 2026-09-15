# quote_service.py

from shippo_client import ShippoClient


def get_shipping_quote(
    origin_zip: str,
    destination_zip: str,
    weight_lb: float,
    length_in: float,
    width_in: float,
    height_in: float
):
    """
    Request shipping rates from Shippo and return only
    business-relevant information.
    """

    client = ShippoClient()

    payload = {
        "address_from": {
            "name": "Honda Distribution Center",
            "street1": "700 Van Ness Ave",
            "city": "Torrance",
            "state": "CA",
            "zip": origin_zip,
            "country": "US"
        },
        "address_to": {
            "name": "Customer",
            "street1": "123 Main Street",
            "city": "Atlanta",
            "state": "GA",
            "zip": destination_zip,
            "country": "US"
        },
        "parcels": [
            {
                "length": str(length_in),
                "width": str(width_in),
                "height": str(height_in),
                "distance_unit": "in",
                "weight": str(weight_lb),
                "mass_unit": "lb"
            }
        ]
    }

    print("PAYLOAD SENT TO SHIPPO")
    print(payload)

    response = client.post(
        "/shipments/",
        payload
    )

    rates = response.get("rates", [])

    # ------------------------------------------------------
    # SUCCESS CASE
    # ------------------------------------------------------

    if rates:

        cheapest_rate = min(
            rates,
            key=lambda rate: float(rate["amount"])
        )

        return {
            "success": True,
            "carrier": cheapest_rate.get(
                "provider",
                "Unknown"
            ),
            "service": cheapest_rate.get(
                "servicelevel",
                {}
            ).get(
                "name",
                "Unknown"
            ),
            "amount": cheapest_rate.get(
                "amount"
            ),
            "currency": cheapest_rate.get(
                "currency"
            ),
            "estimated_days": cheapest_rate.get(
                "estimated_days"
            )
        }

    # ------------------------------------------------------
    # FAILURE CASE
    # ------------------------------------------------------

    shippo_messages = []

    for message in response.get(
        "messages",
        []
    ):

        shippo_messages.append({
            "source": message.get(
                "source",
                "Unknown"
            ),
            "message": message.get(
                "text",
                ""
            )
        })

    return {
        "success": False,
        "message": "No shipping rates available.",
        "shippo_messages": shippo_messages
    }
