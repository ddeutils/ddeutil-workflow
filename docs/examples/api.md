# Extract API

The call stage is the call Python function from any registry location.

## Getting Started

First, you should start create your call.

# RestAPI Integration Examples

This guide demonstrates how to integrate REST APIs into your workflows using call stages and the workflow orchestration system.

## Overview

The workflow system provides powerful capabilities for:

- **API data extraction**: Fetch data from REST endpoints
- **Authentication handling**: OAuth, Bearer tokens, API keys
- **Data transformation**: Process and validate API responses
- **Error handling**: Retry logic and fallback strategies
- **Batch processing**: Handle large datasets efficiently

## Basic API Call

### Simple GET Request

!!! example "Basic API Call"

    === "YAML Workflow"

        ```yaml
        extract-user-data:
          type: Workflow
          params:
            user_id: str
            api_key: str
          jobs:
            get-user:
              stages:
                - name: "Fetch User Data"
                  id: fetch-user
                  uses: api/get-user-data@rest
                  with:
                    url: "https://api.example.com/users/${{ params.user_id }}"
                    headers:
                      Authorization: "Bearer ${{ params.api_key }}"
                      Content-Type: "application/json"
        ```

    === "Python Function"

        ```python
        from ddeutil.workflow import tag, Result
        import requests

        @tag("api", alias="get-user-data")
        def get_user_data(
            url: str,
            headers: dict = None,
            result: Result = None
        ) -> dict:
            """Fetch user data from REST API."""

            response = requests.get(url, headers=headers or {})
            response.raise_for_status()

            data = response.json()
            result.trace.info(f"Retrieved user: {data.get('name')}")

            return {
                "user_data": data,
                "status_code": response.status_code
            }
        ```

## Authentication Examples

### OAuth 2.0 Bearer Token

!!! example "OAuth Authentication"

    === "YAML Workflow"

        ```yaml
        oauth-api-call:
          type: Workflow
          params:
            client_id: str
            client_secret: str
            api_endpoint: str
          jobs:
            authenticate-and-call:
              stages:
                - name: "Get OAuth Token"
                  id: get-token
                  uses: auth/oauth-token@bearer
                  with:
                    token_url: "https://api.example.com/oauth/token"
                    client_id: ${{ params.client_id }}
                    client_secret: ${{ params.client_secret }}
                    scope: "read:users"

                - name: "Call Protected API"
                  id: api-call
                  uses: api/authenticated-call@rest
                  with:
                    url: ${{ params.api_endpoint }}
                    token: ${{ stages.get-token.output.access_token }}
        ```

    === "Python Functions"

        ```python
        from ddeutil.workflow import tag, Result
        import requests

        @tag("auth", alias="oauth-token")
        def get_oauth_token(
            token_url: str,
            client_id: str,
            client_secret: str,
            scope: str = None,
            result: Result = None
        ) -> dict:
            """Get OAuth 2.0 access token."""

            data = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret
            }

            if scope:
                data["scope"] = scope

            response = requests.post(token_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            result.trace.info("OAuth token obtained successfully")

            return {
                "access_token": token_data["access_token"],
                "expires_in": token_data.get("expires_in", 3600)
            }

        @tag("api", alias="authenticated-call")
        def authenticated_api_call(
            url: str,
            token: str,
            method: str = "GET",
            data: dict = None,
            result: Result = None
        ) -> dict:
            """Make authenticated API call."""

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=data
            )
            response.raise_for_status()

            return {
                "data": response.json(),
                "status_code": response.status_code,
                "headers": dict(response.headers)
            }
        ```

## Advanced API Patterns

### Pagination Handling

!!! example "Paginated API Calls"

    === "YAML Workflow"

        ```yaml
        paginated-extraction:
          type: Workflow
          params:
            base_url: str
            api_key: str
            page_size: int
          jobs:
            extract-all-pages:
              stages:
                - name: "Extract Paginated Data"
                  id: paginate
                  uses: api/paginated-extract@rest
                  with:
                    base_url: ${{ params.base_url }}
                    api_key: ${{ params.api_key }}
                    page_size: ${{ params.page_size }}
                    max_pages: 10
        ```

    === "Python Function"

        ```python
        @tag("api", alias="paginated-extract")
        def extract_paginated_data(
            base_url: str,
            api_key: str,
            page_size: int = 100,
            max_pages: int = None,
            result: Result = None
        ) -> dict:
            """Extract data from paginated API."""

            all_data = []
            page = 1
            headers = {"Authorization": f"Bearer {api_key}"}

            while max_pages is None or page <= max_pages:
                url = f"{base_url}?page={page}&size={page_size}"

                response = requests.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()
                items = data.get("items", [])

                if not items:
                    break

                all_data.extend(items)
                result.trace.info(f"Extracted page {page}: {len(items)} items")

                # Check if there are more pages
                if not data.get("has_next", False):
                    break

                page += 1

            result.trace.info(f"Total items extracted: {len(all_data)}")

            return {
                "data": all_data,
                "total_pages": page - 1,
                "total_items": len(all_data)
            }
        ```

### Error Handling and Retries

!!! example "Resilient API Calls"

    === "Python Function with Retries"

        ```python
        import time
        from typing import Optional

        @tag("api", alias="resilient-call")
        def resilient_api_call(
            url: str,
            headers: dict = None,
            max_retries: int = 3,
            retry_delay: float = 1.0,
            timeout: int = 30,
            result: Result = None
        ) -> dict:
            """Make API call with retry logic and error handling."""

            headers = headers or {}
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result.trace.info(f"API call attempt {attempt + 1}")

                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=timeout
                    )

                    # Handle different HTTP status codes
                    if response.status_code == 429:  # Rate limited
                        retry_after = int(response.headers.get("Retry-After", retry_delay))
                        result.trace.warning(f"Rate limited, waiting {retry_after}s")
                        time.sleep(retry_after)
                        continue

                    response.raise_for_status()

                    result.trace.info("API call successful")
                    return {
                        "data": response.json(),
                        "status_code": response.status_code,
                        "attempt": attempt + 1
                    }

                except requests.exceptions.RequestException as e:
                    last_exception = e
                    result.trace.warning(f"Attempt {attempt + 1} failed: {str(e)}")

                    if attempt < max_retries:
                        result.trace.info(f"Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff

            # All retries failed
            result.trace.error(f"All {max_retries + 1} attempts failed")
            raise last_exception
        ```

## Data Processing Examples

### JSON Data Transformation

!!! example "API Response Processing"

    === "YAML Workflow"

        ```yaml
        process-api-data:
          type: Workflow
          params:
            api_url: str
            target_format: str
          jobs:
            extract-and-transform:
              stages:
                - name: "Fetch Raw Data"
                  id: fetch
                  uses: api/get-data@rest
                  with:
                    url: ${{ params.api_url }}

                - name: "Transform Data"
                  id: transform
                  uses: data/transform-json@processor
                  with:
                    input_data: ${{ stages.fetch.output.data }}
                    target_format: ${{ params.target_format }}

                - name: "Validate Results"
                  id: validate
                  uses: data/validate-schema@validator
                  with:
                    data: ${{ stages.transform.output.transformed_data }}
        ```

    === "Python Functions"

        ```python
        from typing import List, Dict, Any
        import json
        from pydantic import BaseModel, ValidationError

        @tag("data", alias="transform-json")
        def transform_json_data(
            input_data: List[Dict[str, Any]],
            target_format: str,
            result: Result = None
        ) -> dict:
            """Transform JSON data to target format."""

            transformed_data = []

            for item in input_data:
                if target_format == "flat":
                    # Flatten nested objects
                    flat_item = {}
                    def flatten(obj, prefix=""):
                        for key, value in obj.items():
                            if isinstance(value, dict):
                                flatten(value, f"{prefix}{key}_")
                            else:
                                flat_item[f"{prefix}{key}"] = value
                    flatten(item)
                    transformed_data.append(flat_item)

                elif target_format == "normalized":
                    # Normalize field names
                    normalized_item = {
                        key.lower().replace(" ", "_"): value
                        for key, value in item.items()
                    }
                    transformed_data.append(normalized_item)

            result.trace.info(f"Transformed {len(transformed_data)} records")

            return {
                "transformed_data": transformed_data,
                "original_count": len(input_data),
                "transformed_count": len(transformed_data)
            }

        class UserSchema(BaseModel):
            id: int
            name: str
            email: str
            active: bool = True

        @tag("data", alias="validate-schema")
        def validate_data_schema(
            data: List[Dict[str, Any]],
            result: Result = None
        ) -> dict:
            """Validate data against Pydantic schema."""

            valid_records = []
            invalid_records = []

            for i, record in enumerate(data):
                try:
                    user = UserSchema(**record)
                    valid_records.append(user.model_dump())
                except ValidationError as e:
                    invalid_records.append({
                        "record_index": i,
                        "record": record,
                        "errors": e.errors()
                    })

            result.trace.info(f"Validation complete: {len(valid_records)} valid, {len(invalid_records)} invalid")

            if invalid_records:
                result.trace.warning(f"Found {len(invalid_records)} invalid records")

            return {
                "valid_records": valid_records,
                "invalid_records": invalid_records,
                "validation_success": len(invalid_records) == 0
            }
        ```

## Batch Processing

### Parallel API Calls

!!! example "Parallel Processing"

    === "YAML Workflow"

        ```yaml
        parallel-api-calls:
          type: Workflow
          params:
            user_ids: list[int]
            api_base_url: str
          jobs:
            process-users:
              strategy:
                matrix:
                  user_id: ${{ params.user_ids }}
                max_workers: 5
              stages:
                - name: "Process User"
                  uses: api/process-single-user@batch
                  with:
                    user_id: ${{ matrix.user_id }}
                    base_url: ${{ params.api_base_url }}
        ```

    === "Python Function"

        ```python
        @tag("api", alias="process-single-user")
        def process_single_user(
            user_id: int,
            base_url: str,
            result: Result = None
        ) -> dict:
            """Process a single user via API."""

            # Get user details
            user_url = f"{base_url}/users/{user_id}"
            user_response = requests.get(user_url)
            user_response.raise_for_status()
            user_data = user_response.json()

            # Get user's orders
            orders_url = f"{base_url}/users/{user_id}/orders"
            orders_response = requests.get(orders_url)
            orders_response.raise_for_status()
            orders_data = orders_response.json()

            # Process and combine data
            processed_data = {
                "user_id": user_id,
                "user_name": user_data.get("name"),
                "email": user_data.get("email"),
                "total_orders": len(orders_data),
                "total_spent": sum(order.get("amount", 0) for order in orders_data)
            }

            result.trace.info(f"Processed user {user_id}: {processed_data['total_orders']} orders")

            return processed_data
        ```

## Configuration and Best Practices

### Environment-based Configuration

!!! example "Configuration Management"

    ```yaml
    # workflow-config.yml
    api-workflow:
      type: Workflow
      params:
        environment: str
        api_timeout: int
      jobs:
        api-call:
          stages:
            - name: "Configure API Call"
              uses: api/configured-call@rest
              with:
                base_url: ${{
                  params.environment == 'prod'
                  and 'https://api.prod.example.com'
                  or 'https://api.dev.example.com'
                }}
                timeout: ${{ params.api_timeout | coalesce(30) }}
                api_key: ${API_KEY}  # From environment variable
    ```

### Error Handling Best Practices

!!! tip "Best Practices"

    1. **Always use timeouts** to prevent hanging requests
    2. **Implement retry logic** with exponential backoff
    3. **Handle rate limiting** by respecting `Retry-After` headers
    4. **Log meaningful messages** for debugging and monitoring
    5. **Validate API responses** before processing
    6. **Use environment variables** for sensitive data like API keys
    7. **Implement circuit breakers** for unreliable APIs
    8. **Cache responses** when appropriate to reduce API calls

### Security Considerations

!!! warning "Security"

    - **Never hardcode credentials** in workflow files
    - **Use environment variables** or secure secret management
    - **Validate and sanitize** all API inputs
    - **Implement proper authentication** for sensitive endpoints
    - **Log requests/responses carefully** to avoid exposing sensitive data
    - **Use HTTPS** for all API communications
    - **Implement rate limiting** to prevent abuse

This comprehensive guide covers the most common API integration patterns in workflow orchestration. Adapt these examples to your specific use cases and API requirements.
