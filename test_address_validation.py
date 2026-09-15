from address_service import validate_address


response = validate_address(
    name="John Doe",
    street1="215 Clayton Street",
    city="San Francisco",
    state="CA",
    zip_code="94117"
)

print(response)