# Shippo External Integration Architecture

## 1. Purpose

`SoftwareArchitecture_API_External` is an independent, locally runnable HTTP
integration service for Shippo. A thin Flask + flask-openapi3 adapter invokes
the existing Python service layer. It is not installed by the main backend API;
the backend uses the integration service through HTTP + JSON only.

The repository is responsible for:

- Exposing local JSON/OpenAPI endpoints on port 8001.
- Loading and validating Shippo configuration.
- Validating addresses, parcels, and quote requests.
- Sending authenticated requests to Shippo.
- Applying conservative retry and rate-limit behavior.
- Converting Shippo responses and failures into typed application results.

It is not responsible for:

- Frontend behavior or the backend API's Flask routes.
- Customer or generator database access.
- Product-specific shipping decisions in `SoftwareArchitecture_Back_End_API`.
- International shipping. Shipment requests are restricted to the US.

## 2. Macro View

```mermaid
flowchart LR
    Caller[HTTP Client]

    subgraph Integration[SoftwareArchitecture_API_External]
      HTTP[Flask + OpenAPI Adapter]
        Services[Service Layer]
        Schemas[Pydantic Schema Layer]
        Client[ShippoClient]
        Config[Configuration]
        Errors[Exceptions and Error Mapping]
    end

    Environment[Process Environment / .env]
    Shippo[Shippo API]

    Caller -->|HTTP + JSON| HTTP
    HTTP --> Services
    Services --> Schemas
    Services --> Client
    Client --> Config
    Client --> Errors
    Client -->|HTTPS + JSON| Shippo
    Shippo -->|HTTP + JSON| Client
    Errors --> Services
    Services --> HTTP
    HTTP -->|JSON + X-Correlation-ID| Caller
    Environment --> Config
```

The normal direction of dependencies is from high-level business operations to
lower-level transport and configuration. The HTTP client does not know about
address validation or shipping-rate selection.

### Shippo status domains and API usage

Shippo's status page reports `Shippo REST API`, `Shippo Web Dashboard`,
`Carrier API`, and `Shippo Platform API` as separate operational domains. These
are monitoring categories, not four required application connections.

| Domain | Use in this architecture |
|---|---|
| Shippo REST API | Called directly at `https://api.goshippo.com` using Shippo token authentication. |
| Shippo Web Dashboard | Not called; it is an operator-facing Shippo web application. |
| Carrier API | Used indirectly when Shippo requests rates or other operations from carriers. |
| Shippo Platform API | Not called; platform-partner and embedded-shipping features are outside scope. |

The production service paths are `POST /addresses/` and `POST /shipments/`.
The opt-in live integration test also calls `GET /carrier_accounts/`. Therefore,
REST API availability directly affects all Shippo operations, while a Carrier
API outage can selectively affect rates even when the Shippo REST API remains
reachable. Status labels describe current provider health and should be read
from [Shippo's status page](https://status.goshippo.com/) rather than treated as
permanent architecture state.

Local development serves this adapter on `127.0.0.1:8001`. In Compose,
Gunicorn binds container port `8001` under the private service name
`shippo-integration`; no host port is published. The backend is its only
application caller, and this container alone receives `SHIPPO_API_KEY`. The
health route checks HTTP process liveness without loading Shippo settings.

## 3. Layered Architecture

```text
HTTP Client
  |
  v
app.py                    HTTP validation, correlation, status mapping
  |
  v
api_schemas/              HTTP-only request/response contracts
  |
  v
services/                 Business operations and response interpretation
  |
  +--> schemas/           Input validation and typed result contracts
  +--> client.py          HTTP transport, retries, tracing, and JSON decoding
           |
           +--> config.py
           +--> exceptions.py
           |
           v
        Shippo API
```

### 3.1 HTTP Adapter Layer

File: `app.py`

Responsibilities:

- Expose `/`, `/health`, `/validate-address`, and `/shipping-quote`.
- Validate JSON through API-specific Pydantic models.
- Create or reuse one HTTP correlation ID.
- Pass the ID explicitly through services to Shippo.
- Map stable business error codes to HTTP statuses.
- Serialize internal typed results into JSON-safe dictionaries.

The routes do not build Shippo payloads, implement retries, load backend data,
or select rates.

HTTP outcomes are defined at this boundary:

| Condition | Status |
|---|---:|
| Successful operation | `200` |
| `NO_RATES` or `INVALID_ADDRESS` business outcome | `200` |
| Request model validation failure | `422` |
| POST body is not `application/json` | `415` |
| `CONFIGURATION_ERROR` | `503` |
| `SHIPPO_TIMEOUT` | `504` |
| `SHIPPO_FAILURE` | `502` |
| Unexpected route defect | `500` |

Directory: `api_schemas/`

These models describe only the public HTTP contract. Internal provider models
remain under `shippo_integration/schemas/`.

### 3.2 Configuration Layer

File: `shippo_integration/config.py`

Responsibilities:

- Load the repository-level `.env` without replacing existing process values.
- Validate Shippo credentials and transport settings.
- Return immutable `ShippoSettings` and HTTP server settings.

Configuration precedence is:

1. Existing process environment variables, which `.env` never replaces.
2. Values from `.env` when the process does not already define the variable.
3. Safe transport defaults where documented.

Shipping addresses are request data. Configuration errors represent actual
integration settings such as a missing or invalid Shippo credential.

### 3.3 Internal Schema Layer

Directory: `shippo_integration/schemas/`

| Module | Responsibility |
|---|---|
| `address.py` | Generic Shippo address input and typed address-validation result |
| `parcel.py` | Parcel measurements and unit fields |
| `shipping_quote.py` | Complete US shipment validation and typed quote results |
| `error.py` | Stable machine-readable business error codes |

`AddressSchema` is intentionally flexible because Shippo can return or accept
partial/extended address objects. `ShippingQuoteRequestSchema` is stricter: it
requires complete origin and destination fields before a rate request.

### 3.4 Service Layer

Directory: `shippo_integration/services/`

| Module | Public operation | Responsibility |
|---|---|---|
| `address.py` | `validate_address(...)` | Build an address payload and interpret validation results |
| `shipping.py` | `get_shipping_quote(address_from, address_to, parcels)` | Validate the complete shipment, request rates, and select the cheapest rate |
| `error_mapping.py` | Internal helper | Convert adapter exceptions to stable business codes/messages |

Services return typed Pydantic models:

- `AddressValidationResult`
- `ShippingQuoteResult`
- `ShippingErrorResult`

### 3.5 HTTP Client Layer

File: `shippo_integration/client.py`

`ShippoClient` owns all HTTP behavior:

- Authentication headers.
- URL normalization.
- Correlation IDs.
- Request latency logging.
- Method-aware retry behavior.
- `Retry-After` parsing.
- HTTP and JSON response validation.
- Translation to adapter exceptions.

Its public interface remains small:

```python
client.get(endpoint)
client.post(endpoint, payload)
```

Both methods return decoded Shippo JSON objects as dictionaries.

### 3.6 Exception and Business Error Layers

File: `shippo_integration/exceptions.py`

Adapter exceptions describe technical failures:

- `ShippoConfigurationError`
- `ShippoTimeoutError`
- `ShippoAPIError`
- `ShippoResponseError`

File: `shippo_integration/services/error_mapping.py`

Services convert those exceptions into stable business codes:

| Condition | Business code |
|---|---|
| Missing/invalid configuration | `CONFIGURATION_ERROR` |
| Request timeout | `SHIPPO_TIMEOUT` |
| Network, HTTP, or malformed provider response | `SHIPPO_FAILURE` |
| Shippo returns no rates | `NO_RATES` |
| Shippo rejects an address | `INVALID_ADDRESS` |

## 4. Module Dependency View

```mermaid
flowchart TD
  App[app.py]
  APISchemas[api_schemas/]
    Package[shippo_integration/__init__.py]
    ServiceExports[services/__init__.py]
    AddressService[services/address.py]
    ShippingService[services/shipping.py]
    ErrorMapping[services/error_mapping.py]
    Client[client.py]
    Config[config.py]
    Exceptions[exceptions.py]
    AddressSchema[schemas/address.py]
    ParcelSchema[schemas/parcel.py]
    QuoteSchema[schemas/shipping_quote.py]
    ErrorSchema[schemas/error.py]

    App --> APISchemas
    App --> ServiceExports
    Package --> Client
    Package --> Exceptions
    ServiceExports --> AddressService
    ServiceExports --> ShippingService

    AddressService --> Client
    AddressService --> AddressSchema
    AddressService --> ErrorMapping

    ShippingService --> Client
    ShippingService --> AddressSchema
    ShippingService --> ParcelSchema
    ShippingService --> QuoteSchema
    ShippingService --> ErrorMapping

    QuoteSchema --> AddressSchema
    QuoteSchema --> ParcelSchema
    QuoteSchema --> ErrorSchema
    ErrorMapping --> Exceptions
    ErrorMapping --> ErrorSchema
    Client --> Config
    Client --> Exceptions
```

## 5. End-to-End Shipping Quote Example

### 5.1 HTTP Caller Input

The caller supplies complete origin and destination addresses plus one or more
parcels. No shipping address comes from environment configuration.

```http
POST /shipping-quote HTTP/1.1
Host: 127.0.0.1:8001
Content-Type: application/json
X-Correlation-ID: order-123

{
  "address_from": {
    "name": "Origin Company",
    "street1": "123 Origin Street",
    "city": "Torrance",
    "state": "CA",
    "zip": "90504",
    "country": "US"
  },
  "address_to": {
    "name": "Customer Company",
    "street1": "456 Destination Street",
    "city": "Atlanta",
    "state": "GA",
    "zip": "30301",
    "country": "US"
  },
  "parcels": [
    {
      "length": "24",
      "width": "16",
      "height": "12",
      "distance_unit": "in",
      "weight": "12",
      "mass_unit": "lb"
    }
  ]
}
```

Country may be omitted. The shipping schema inserts `country: "US"` for both
origin and destination. An explicitly non-US country is rejected before Shippo
is called.

Parcel measurements may be strings, integers, or floating-point numbers. The
example uses strings because Shippo commonly represents measurements that way.

The shipping endpoint uses `zip` inside `address_from` and `address_to`.
The address-validation endpoint uses the separate top-level field `zip_code`.

### 5.2 Address Ownership

Each HTTP request supplies complete origin and destination addresses. The
backend supplies parcel measurements loaded from its database. No operational
address is stored in integration-service configuration.

### 5.3 Request Sequence

```mermaid
sequenceDiagram
    autonumber
  participant Caller as HTTP Client
  participant App as app.py
  participant APIModel as api_schemas
    participant Shipping as services/shipping.py
    participant Schema as ShippingQuoteRequestSchema
    participant Client as ShippoClient
    participant Shippo

    Caller->>App: POST /shipping-quote + JSON + X-Correlation-ID
    App->>APIModel: Validate HTTP request body
    APIModel-->>App: Origin, destination, and parcels
    App->>Shipping: get_shipping_quote(..., correlation_id)
    Shipping->>Schema: Validate origin + destination + parcels
    Schema->>Schema: Require complete addresses
    Schema->>Schema: Force country = US
    Schema-->>Shipping: Validated request model
    Shipping->>Shipping: model_dump(by_alias=True, ...)
    Shipping->>Client: post("/shipments/", payload, correlation_id)
    Client->>Client: Reuse HTTP correlation ID
    Client->>Client: Start latency timer
    Client->>Shippo: POST /shipments/ + JSON + X-Correlation-ID
    Shippo-->>Client: Shipment response with rates
    Client->>Client: Validate HTTP and JSON object
    Client-->>Shipping: Raw response dictionary
    Shipping->>Shipping: Select lowest numeric amount
    Shipping-->>App: ShippingQuoteResult
    App->>APIModel: Adapt typed result
    App-->>Caller: HTTP 200 + JSON + X-Correlation-ID
```

### 5.4 Exact Shippo Payload Shape

The service sends this structure to `/shipments/`:

```json
{
  "address_from": {
    "name": "Origin Company",
    "street1": "123 Origin Street",
    "city": "Torrance",
    "state": "CA",
    "zip": "90504",
    "country": "US"
  },
  "address_to": {
    "name": "Customer Company",
    "street1": "456 Destination Street",
    "city": "Atlanta",
    "state": "GA",
    "zip": "30301",
    "country": "US"
  },
  "parcels": [
    {
      "length": "24",
      "width": "16",
      "height": "12",
      "distance_unit": "in",
      "weight": "12",
      "mass_unit": "lb"
    }
  ]
}
```

### 5.5 Successful Typed Result

```python
if result.success:
    print(result.carrier)
    print(result.amount)
```

The result type is `ShippingQuoteResult`:

```json
{
  "success": true,
  "carrier": "USPS",
  "service": "Priority",
  "amount": "12.00",
  "currency": "USD",
  "estimated_days": 3
}
```

Serialize at an API boundary with:

```python
response_body = result.model_dump(exclude_unset=True)
# Flask serializes this dictionary into the HTTP JSON response.
```

### 5.6 Failure Paths

```mermaid
flowchart TD
    Start[Shipping Quote Request]
    Addresses{Origin and destination complete and US?}
    Parcel{Complete positive parcel data?}
    Config{Shippo credential and transport settings valid?}
    Client[Call Shippo]
    Rates{Rates returned?}
    Success[ShippingQuoteResult]
    ConfigError[ShippingErrorResult: CONFIGURATION_ERROR]
    ValidationError[Pydantic ValidationError]
    ProviderError[ShippingErrorResult: timeout/failure]
    NoRates[ShippingErrorResult: NO_RATES]

    Start --> Addresses
    Addresses -->|No| ValidationError
    Addresses -->|Yes| Parcel
    Parcel -->|No| ValidationError
    Parcel -->|Yes| Config
    Config -->|No| ConfigError
    Config -->|Yes| Client
    Client -->|Technical failure| ProviderError
    Client -->|Response| Rates
    Rates -->|Yes| Success
    Rates -->|No| NoRates
```

## 6. End-to-End Address Validation Example

```http
POST /validate-address HTTP/1.1
Host: 127.0.0.1:8001
Content-Type: application/json

{
  "customer_name": "Customer Company",
  "street1": "123 Main Street",
  "city": "Atlanta",
  "state": "GA",
  "zip_code": "30301",
  "country": "US"
}
```

Sequence:

```mermaid
sequenceDiagram
    autonumber
    participant Caller as HTTP Client
    participant App as app.py
    participant APIModel as AddressValidationRequestSchema
    participant Address as services/address.py
    participant Schema as AddressSchema
    participant Client as ShippoClient
    participant Shippo

    Caller->>App: POST /validate-address + JSON
    App->>APIModel: Validate HTTP request body
    APIModel-->>App: Normalized US address
    App->>Address: validate_address(..., correlation_id)
    Address->>Schema: Validate fields and set validate=True
    Schema-->>Address: AddressSchema
    Address->>Client: post("/addresses/", payload, correlation_id)
    Client->>Shippo: POST /addresses/
    Shippo-->>Client: Address validation response
    Client-->>Address: Raw response dictionary
    Address->>Address: Normalize optional validation metadata
    Address-->>App: AddressValidationResult
    App->>App: Rename zip to normalized_zip and map status
    App-->>Caller: JSON + X-Correlation-ID
```

Possible outcomes are:

- Valid address: `success=True`, `valid=True`.
- Invalid address: `success=False`, `error_code="INVALID_ADDRESS"`.
- Timeout: `success=False`, `error_code="SHIPPO_TIMEOUT"`.
- Provider/HTTP failure: `success=False`, `error_code="SHIPPO_FAILURE"`.
- Missing client configuration: `success=False`, `error_code="CONFIGURATION_ERROR"`.

## 7. HTTP Retry and Observability Flow

Every `get()` or `post()` call sends an `X-Correlation-ID`. A caller-supplied ID
is preserved; otherwise `ShippoClient` generates a UUID. The same identifier is
reused for all attempts belonging to that logical request.

```mermaid
flowchart TD
    Call[Client get/post]
    ID[Reuse supplied ID or generate UUID]
    Attempt[Execute HTTP attempt]
    Result{Outcome}
    Retry{Method and failure retryable?}
    Delay[Retry-After or exponential delay]
    Parse[Decode JSON object]
    Return[Return dictionary]
    Raise[Raise existing adapter exception]
    Log[Log terminal latency and outcome]

    Call --> ID --> Attempt --> Result
    Result -->|HTTP success| Parse
    Parse -->|Valid object| Log --> Return
    Parse -->|Invalid JSON/object| Log --> Raise
    Result -->|Failure| Retry
    Retry -->|Yes, attempts remain| Delay --> Attempt
    Retry -->|No| Log --> Raise
```

Retry policy:

| Method | Retried conditions |
|---|---|
| GET | Timeout, connection/chunk failure, HTTP 429/502/503/504 |
| POST | HTTP 429 only |

POST does not retry ambiguous network, timeout, gateway, or response-decoding
failures because Shippo may already have created the address or shipment.

Logs include:

- Correlation ID.
- Method and endpoint path.
- Attempt count.
- Retry category and delay.
- Terminal outcome.
- Total latency in milliseconds.

Logs exclude credentials, headers, payloads, response bodies, query strings,
and raw exception text.

## 8. Configuration Summary

| Variable | Required | Purpose |
|---|---:|---|
| `INTEGRATION_API_HOST` | No | HTTP bind host; default 127.0.0.1 |
| `INTEGRATION_API_PORT` | No | HTTP port; default 8001 |
| `INTEGRATION_API_DEBUG` | No | Local Flask debug flag |
| `SHIPPO_API_KEY` | Yes | Shippo authentication |
| `SHIPPO_BASE_URL` | No | Shippo API base URL |
| `SHIPPO_TIMEOUT_SECONDS` | No | Timeout for one HTTP attempt |
| `SHIPPO_MAX_ATTEMPTS` | No | Total attempts for retryable requests |
| `SHIPPO_BACKOFF_SECONDS` | No | Exponential retry base delay |
| `SHIPPO_MAX_RETRY_AFTER_SECONDS` | No | Maximum honored provider delay |

## 9. Testing Architecture

```text
tests/
  test_http_endpoints.py   Flask test-client coverage for integration routes
  unit/
    test_config.py          Credential, transport, and HTTP server configuration
    test_client.py          HTTP, retries, correlation, latency, redaction
    test_schemas.py         Request and typed response contracts
    test_services.py        Service payloads, outcomes, and error mapping
    test_documentation.py   Required module/class/function docstrings
  integration/
    test_shippo_connection.py  Opt-in real Shippo connectivity
```

Unit tests use mocks and do not contact Shippo. The integration test runs only
when `RUN_SHIPPO_INTEGRATION=1` is explicitly set.

## 10. Design Rules for Future Changes

1. Keep HTTP behavior inside `ShippoClient`.
2. Keep HTTP routes thin: validate, call services, map status, serialize.
3. Keep provider-independent decisions inside services.
4. Validate data before calling Shippo.
5. Require complete origin, destination, and parcel data at the HTTP boundary.
6. Preserve the US-only country rule unless international support is designed
   explicitly across schemas, services, tests, and documentation.
7. Return typed service models and serialize only at API boundaries.
8. Branch on stable business error codes, not message text.
9. Never log credentials, payloads, response bodies, or personal address data.
10. Keep POST retries conservative to avoid duplicate provider resources.
11. Add mocked tests for every new HTTP/provider response or failure path.

## 11. Schema and Service Class Model

The integration has two contract levels. `api_schemas/` describes the local
HTTP interface, while `shippo_integration/schemas/` describes reusable service
and provider-facing data. HTTP response models adapt internal results instead
of exposing them directly.

```mermaid
classDiagram
  class AddressValidationRequestSchema {
    +str customer_name
    +str street1
    +str city
    +str state
    +str zip_code
    +str country = US
  }

  class AddressValidationResponseSchema {
    +bool success
    +bool valid
    +str|null normalized_zip
    +bool|null is_residential
    +list messages
    +BusinessErrorCode|null error_code
    +str|null message
    +from_result(result)
  }

  class AddressSchema {
    +str|null name
    +str|null street1
    +str|null city
    +str|null state
    +str|null zip
    +str|null country
    +bool|null validate_address
  }

  class ParcelSchema {
    +Measurement|null length
    +Measurement|null width
    +Measurement|null height
    +str|null distance_unit
    +Measurement|null weight
    +str|null mass_unit
  }

  class ShippingQuoteRequestSchema {
    +AddressSchema address_from
    +AddressSchema address_to
    +ParcelSchema[] parcels
    +validate_complete_addresses()
  }

  class AddressValidationResult {
    +bool success
    +bool valid
    +str|null zip
    +bool|null is_residential
    +list messages
    +BusinessErrorCode|null error_code
    +str|null message
  }

  class BusinessErrorSchema {
    +bool success
    +BusinessErrorCode error_code
    +str message
  }

  class ShippingQuoteResult {
    +true success
    +str|null carrier
    +str|null service
    +str|null amount
    +str|null currency
    +int|null estimated_days
  }

  class ShippingErrorResult {
    +dict[] shippo_messages
  }

  ShippingQuoteRequestSchema *-- AddressSchema
  ShippingQuoteRequestSchema *-- ParcelSchema
  ShippingErrorResult --|> BusinessErrorSchema
  AddressValidationRequestSchema ..> AddressSchema : service builds
  AddressValidationResult ..> AddressValidationResponseSchema : adapted to
```

Generic `AddressSchema` and `ParcelSchema` models preserve unknown provider
extensions and permit partial objects. `ShippingQuoteRequestSchema` is the
aggregate boundary that requires complete addresses, at least one parcel,
finite positive measurements, distance units `in` or `cm`, and mass units
`lb`, `oz`, `kg`, or `g`.

| Service operation | Input | Typed result |
|---|---|---|
| `validate_address(...)` | Name, street, city, state, ZIP, country, optional client/correlation ID | `AddressValidationResult` |
| `get_shipping_quote(...)` | Origin, destination, parcels, optional client/correlation ID | `ShippingQuoteResult` or `ShippingErrorResult` |

## 12. Address Payload and Response Transformation

The address route deliberately uses caller-friendly `customer_name` and
`zip_code` fields. The service translates them to Shippo's `name` and `zip`
keys and aliases `validate_address` back to Shippo's `validate` key.

```mermaid
flowchart LR
  HTTP[HTTP request<br/>customer_name, zip_code]
  API[AddressValidationRequestSchema<br/>trim text, uppercase state/country]
  Internal[AddressSchema<br/>name, zip, validate_address]
  Provider[Shippo JSON<br/>name, zip, validate]
  Result[AddressValidationResult<br/>zip]
  Response[HTTP response<br/>normalized_zip]

  HTTP --> API --> Internal --> Provider
  Provider --> Result --> Response
```

Exact provider request:

```json
{
  "name": "Customer Company",
  "street1": "123 Main Street",
  "city": "Atlanta",
  "state": "GA",
  "zip": "30301",
  "country": "US",
  "validate": true
}
```

Valid HTTP result:

```json
{
  "success": true,
  "valid": true,
  "normalized_zip": "30301-1234",
  "is_residential": false,
  "messages": []
}
```

Invalid real-world address result:

```json
{
  "success": false,
  "valid": false,
  "normalized_zip": null,
  "is_residential": null,
  "messages": [
  {"text": "Street could not be validated."}
  ],
  "error_code": "INVALID_ADDRESS",
  "message": "Shippo could not validate the supplied address."
}
```

## 13. Correlation ID Propagation

```mermaid
sequenceDiagram
  autonumber
  participant Caller
  participant Flask as app.py
  participant Service
  participant Client as ShippoClient
  participant Shippo

  Caller->>Flask: Request + optional X-Correlation-ID
  Flask->>Flask: Accept usable ID or generate UUID
  Flask->>Service: Operation(..., correlation_id)
  Service->>Client: get/post(..., correlation_id)
  Client->>Shippo: HTTPS + same X-Correlation-ID
  alt Retryable response
    Client->>Shippo: Retry with same X-Correlation-ID
  end
  Shippo-->>Client: Provider response
  Client-->>Service: Decoded dictionary
  Service-->>Flask: Typed result
  Flask-->>Caller: JSON + same X-Correlation-ID
```

The identifier joins backend, integration, retry, and response logs without
logging personal address data. It is tracing metadata, not authentication.

## 14. Retry Decision Model

```mermaid
flowchart TD
  A[Execute Shippo request] --> B{Outcome}
  B -- Successful HTTP --> C{JSON object?}
  C -- Yes --> D[Return dictionary]
  C -- No --> E[Raise ShippoResponseError]
  B -- HTTP error --> F{Method and status}
  F -- GET 429/502/503/504 --> G{Attempts remain?}
  F -- POST 429 --> G
  F -- Other status --> H[Raise ShippoAPIError]
  B -- Timeout/connection/chunk error --> I{GET request?}
  I -- Yes --> G
  I -- No --> J[Raise timeout or API error]
  G -- Yes --> K[Retry-After or exponential delay]
  K --> A
  G -- No --> L[Raise exhausted failure]
```

| Event | `GET` | `POST` | Reason |
|---|---|---|---|
| HTTP `429` | Retry | Retry | Explicit provider rate limit |
| HTTP `502`, `503`, `504` | Retry | Stop | POST may already have created a resource |
| Timeout/connection/chunk failure | Retry | Stop | Ambiguous POST replay is unsafe |
| Invalid successful JSON | Stop | Stop | Retrying cannot establish response correctness |
| Other HTTP error | Stop | Stop | Not part of the retry policy |

Fallback delay before retry number $n$ is exponential:

$$
	ext{delay}_n = \text{SHIPPO_BACKOFF_SECONDS} \times 2^{n-1}
$$

`Retry-After` seconds or HTTP dates take precedence when valid, and all delays
are capped by `SHIPPO_MAX_RETRY_AFTER_SECONDS`.

## 15. Exception Translation and HTTP Outcomes

```mermaid
flowchart LR
  Config[ShippoConfigurationError] --> Map[map_shippo_exception]
  Timeout[ShippoTimeoutError] --> Map
  API[ShippoAPIError] --> Map
  Response[ShippoResponseError] --> Map

  Map --> Configuration[CONFIGURATION_ERROR]
  Map --> TimedOut[SHIPPO_TIMEOUT]
  Map --> Failure[SHIPPO_FAILURE]

  Configuration --> HTTP503[HTTP 503]
  TimedOut --> HTTP504[HTTP 504]
  Failure --> HTTP502[HTTP 502]
```

`NO_RATES` and `INVALID_ADDRESS` are completed business outcomes and use HTTP
`200`. Technical failures use `502`, `503`, or `504`. Callers should branch on
`error_code`; message text is intended for people and may evolve.

The route layer catches unexpected defects separately and returns `500` without
exposing stack traces, credentials, raw provider payloads, or exception text.
