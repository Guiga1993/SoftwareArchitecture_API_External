"""Expose the Shippo integration layer through a thin local HTTP API.

Routes validate HTTP JSON, call existing business services, adapt typed results,
and map stable business error codes to status codes. Provider payloads, retries,
rate selection, and configuration remain in ``shippo_integration``.
"""

import logging
import time
import uuid

from flask import Response, g, redirect, request
from flask_openapi3 import Info, OpenAPI, Tag  # type: ignore[attr-defined]

from api_schemas import (
    AddressValidationRequestSchema,
    AddressValidationResponseSchema,
    HealthResponseSchema,
    ShippingQuoteErrorResponseSchema,
    ShippingQuoteRequestSchema,
    ShippingQuoteResponseSchema,
    ShippingQuoteSuccessResponseSchema,
)
from shippo_integration.config import get_integration_api_settings
from shippo_integration.schemas.error import BusinessErrorCode
from shippo_integration.schemas.shipping_quote import ShippingErrorResult
from shippo_integration.services import get_shipping_quote, validate_address


logger = logging.getLogger("shippo-integration-api")
CORRELATION_HEADER = "X-Correlation-ID"
MAX_CORRELATION_ID_LENGTH = 128
JSON_ENDPOINTS = frozenset({"validate_address_route", "shipping_quote_route"})


def _correlation_id_from_request() -> str:
    """Return a bounded caller identifier or generate a request-scoped UUID."""
    supplied = request.headers.get(CORRELATION_HEADER, "").strip()
    if supplied and len(supplied) <= MAX_CORRELATION_ID_LENGTH:
        return supplied
    return str(uuid.uuid4())


def _status_for_error_code(error_code: BusinessErrorCode | None) -> int:
    """Map stable service outcomes to their HTTP status at one boundary."""
    return {
        "NO_RATES": 200,
        "INVALID_ADDRESS": 200,
        "CONFIGURATION_ERROR": 503,
        "SHIPPO_TIMEOUT": 504,
        "SHIPPO_FAILURE": 502,
    }.get(error_code, 200)


def _shipping_unexpected_error() -> tuple[dict[str, object], int]:
    """Return a safe typed-shape failure for an unexpected route defect."""
    result = ShippingQuoteErrorResponseSchema(
        success=False,
        error_code="SHIPPO_FAILURE",
        message="Unexpected server error.",
        shippo_messages=[],
    )
    return result.model_dump(exclude_unset=True), 500


def _address_unexpected_error() -> tuple[dict[str, object], int]:
    """Return a safe address-shape failure for an unexpected route defect."""
    result = AddressValidationResponseSchema(
        success=False,
        valid=False,
        normalized_zip=None,
        is_residential=None,
        messages=[],
        error_code="SHIPPO_FAILURE",
        message="Unexpected server error.",
    )
    return result.model_dump(exclude_unset=True), 500


def create_app() -> OpenAPI:
    """Create the local OpenAPI application without validating Shippo readiness."""
    application = OpenAPI(
        __name__,
        info=Info(title="Shippo Integration API", version="1.0.0"),
    )
    application.json.sort_keys = False  # type: ignore[assignment]

    health_tag = Tag(name="Health", description="HTTP process liveness.")
    address_tag = Tag(
        name="Address Validation",
        description="Validate and normalize US postal addresses through Shippo.",
    )
    shipping_tag = Tag(
        name="Shipping Quote",
        description="Request the cheapest rate for a complete US shipment.",
    )

    @application.before_request
    def begin_request_context():
        """Initialize request-scoped tracing and reject non-JSON POST bodies."""
        g.correlation_id = _correlation_id_from_request()
        g.request_started_at = time.perf_counter()
        if request.endpoint in JSON_ENDPOINTS and not request.is_json:
            return {
                "success": False,
                "error_code": "SHIPPO_FAILURE",
                "message": "Content-Type must be application/json.",
            }, 415
        return None

    @application.after_request
    def finish_request_context(response: Response) -> Response:
        """Return correlation metadata and log safe HTTP outcome/latency fields."""
        correlation_id = getattr(g, "correlation_id", None) or str(uuid.uuid4())
        started_at = getattr(g, "request_started_at", None)
        if started_at is None:
            started_at = time.perf_counter()
        latency_ms = (time.perf_counter() - started_at) * 1000
        response.headers[CORRELATION_HEADER] = correlation_id
        logger.info(
            "HTTP request correlation_id=%s method=%s path=%s status=%d "
            "latency_ms=%.2f outcome=http_%d",
            correlation_id,
            request.method,
            request.path,
            response.status_code,
            latency_ms,
            response.status_code,
        )
        return response

    @application.get("/", tags=[health_tag])  # type: ignore[misc]
    def root():
        """Redirect callers to the flask-openapi3 documentation selector."""
        return redirect("/openapi")

    @application.get(  # type: ignore[misc]
        "/health",
        tags=[health_tag],
        responses={"200": HealthResponseSchema},
    )
    def health():
        """Report HTTP process liveness without checking Shippo configuration."""
        return HealthResponseSchema().model_dump(), 200

    @application.post(  # type: ignore[misc]
        "/validate-address",
        tags=[address_tag],
        responses={
            "200": AddressValidationResponseSchema,
            "500": AddressValidationResponseSchema,
            "502": AddressValidationResponseSchema,
            "503": AddressValidationResponseSchema,
            "504": AddressValidationResponseSchema,
        },
    )
    def validate_address_route(body: AddressValidationRequestSchema):
        """Validate an HTTP address by delegating to the existing service."""
        try:
            result = validate_address(
                name=body.customer_name,
                street1=body.street1,
                city=body.city,
                state=body.state,
                zip_code=body.zip_code,
                country=body.country,
                correlation_id=g.correlation_id,
            )
            response = AddressValidationResponseSchema.from_result(result)
            return (
                response.model_dump(exclude_unset=True),
                _status_for_error_code(result.error_code),
            )
        except Exception:
            logger.error(
                "Unexpected address route failure correlation_id=%s",
                g.correlation_id,
            )
            return _address_unexpected_error()

    @application.post(  # type: ignore[misc]
        "/shipping-quote",
        tags=[shipping_tag],
        responses={
            "200": ShippingQuoteResponseSchema,
            "500": ShippingQuoteErrorResponseSchema,
            "502": ShippingQuoteErrorResponseSchema,
            "503": ShippingQuoteErrorResponseSchema,
            "504": ShippingQuoteErrorResponseSchema,
        },
    )
    def shipping_quote_route(body: ShippingQuoteRequestSchema):
        """Delegate a complete validated shipment to the shipping service."""
        try:
            result = get_shipping_quote(
                address_from=body.address_from.model_dump(exclude_unset=True),
                address_to=body.address_to.model_dump(exclude_unset=True),
                parcels=[parcel.model_dump(exclude_unset=True) for parcel in body.parcels],
                correlation_id=g.correlation_id,
            )
            if isinstance(result, ShippingErrorResult):
                response = ShippingQuoteErrorResponseSchema.from_result(result)
                return (
                    response.model_dump(exclude_unset=True),
                    _status_for_error_code(result.error_code),
                )
            response = ShippingQuoteSuccessResponseSchema.from_result(result)
            return response.model_dump(exclude_unset=True), 200
        except Exception:
            logger.error(
                "Unexpected shipping route failure correlation_id=%s",
                g.correlation_id,
            )
            return _shipping_unexpected_error()

    return application


app = create_app()


if __name__ == "__main__":
    settings = get_integration_api_settings()
    app.run(host=settings.host, port=settings.port, debug=settings.debug)