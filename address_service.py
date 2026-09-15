from shippo_client import ShippoClient


def validate_address(
    name,
    street1,
    city,
    state,
    zip_code,
    country="US"
):

    client = ShippoClient()

    payload = {
        "name": name,
        "street1": street1,
        "city": city,
        "state": state,
        "zip": zip_code,
        "country": country,
        "validate": True
    }

    response = client.post(
        "/addresses/",
        payload
    )

    return {
        "valid":
            response["validation_results"]["is_valid"],

        "zip":
            response["zip"],

        "is_residential":
            response["is_residential"]
    }