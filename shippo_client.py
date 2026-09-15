import requests

from config import (
    SHIPPO_API_KEY,
    SHIPPO_BASE_URL
)


class ShippoClient:

    def __init__(self):

        self.base_url = SHIPPO_BASE_URL

        self.headers = {
            "Authorization": f"ShippoToken {SHIPPO_API_KEY}",
            "Content-Type": "application/json"
        }

    def post(
        self,
        endpoint: str,
        payload: dict
    ):

        url = f"{self.base_url}{endpoint}"

        response = requests.post(
            url,
            json=payload,
            headers=self.headers,
            timeout=30
        )

        response.raise_for_status()

        return response.json()

    def get(
        self,
        endpoint: str
    ):

        url = f"{self.base_url}{endpoint}"

        response = requests.get(
            url,
            headers=self.headers,
            timeout=30
        )

        response.raise_for_status()

        return response.json()