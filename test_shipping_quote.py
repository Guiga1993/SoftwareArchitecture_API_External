# test_shipping_quote.py

from quote_service import get_shipping_quote


response = get_shipping_quote(
    origin_zip="90501",
    destination_zip="30301",
    weight_lb=12,
    length_in=48,
    width_in=40,
    height_in=60
)

print(response)