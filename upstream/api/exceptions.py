"""
Custom exception handler for standardized API error responses.

Provides consistent error format across all API endpoints with RFC 7807 alignment:
{
    "error": {
        "code": "validation_error",
        "message": "Invalid input data",
        "details": {"field_name": ["error message"]},
        "type": "/errors/validation-error",  // Optional RFC 7807 type URI
        "request_id": "abc123"  // Optional for debugging
    }
}

The error response format includes:
- code: Machine-readable error code (e.g., validation_error, not_found)
- message: Human-readable error message
- details: Optional field-level errors or additional context
- type: Optional RFC 7807 problem type URI for error documentation
- request_id: Optional request ID from RequestIdMiddleware for support tracking
"""

from rest_framework.views import exception_handler
from rest_framework.exceptions import (
    ValidationError,
    NotFound,
    PermissionDenied,
    AuthenticationFailed,
    NotAuthenticated,
    ParseError,
    MethodNotAllowed,
    NotAcceptable,
    UnsupportedMediaType,
    Throttled,
)
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns standardized error responses.

    Enhances error responses with request tracking and RFC 7807 alignment.
    Extracts request_id from middleware for debugging support, and includes
    optional type URI for error documentation.

    Args:
        exc: The exception instance
        context: Dict containing 'view' and 'request' keys

    Returns:
        Response object with standardized error format including:
        - code: Machine-readable error code
        - message: Human-readable description
        - details: Field-level errors or additional context
        - type: Optional RFC 7807 problem type URI
        - request_id: Optional request ID for support tracking
    """
    # Extract request_id from middleware if available
    request_id = None
    if context and "request" in context:
        request = context["request"]
        request_id = getattr(request, "id", None)  # From RequestIdMiddleware

    # Call DRF's default exception handler first to get the standard error response
    response = exception_handler(exc, context)

    # If DRF didn't handle it, check for Django exceptions
    if response is None:
        if isinstance(exc, Http404):
            error_code = "not_found"
            error_message = "The requested resource was not found."
            status_code = 404
            details = None
        elif isinstance(exc, DjangoPermissionDenied):
            error_code = "permission_denied"
            error_message = "You do not have permission to perform this action."
            status_code = 403
            details = None
        else:
            # Unhandled exception - log it and return generic 500 error
            logger.error(
                f"Unhandled exception: {exc.__class__.__name__}: {str(exc)}",
                exc_info=True,
                extra={
                    "view": context.get("view"),
                    "request": context.get("request"),
                    "request_id": request_id,
                },
            )
            error_code = "internal_server_error"
            error_message = "An unexpected error occurred. Please try again later."
            status_code = 500
            # Include request_id in details for 500 errors to aid debugging
            details = {"request_id": request_id} if request_id else None

        # Create standardized response with RFC 7807 type and request tracking
        error_data = {
            "code": error_code,
            "message": error_message,
            "details": details,
            "type": _get_error_type_uri(error_code),
        }
        if request_id:
            error_data["request_id"] = request_id

        response = Response(
            {"error": error_data},
            status=status_code,
        )
        return response

    # Transform DRF error responses to our standard format
    error_data = get_error_data(exc, response, context)

    # Add RFC 7807 type URI
    error_data["type"] = _get_error_type_uri(error_data["code"])

    # Add request_id if available
    if request_id:
        error_data["request_id"] = request_id

    response.data = {"error": error_data}

    return response


def _get_error_type_uri(error_code):
    """
    Generate RFC 7807 problem type URI for error documentation.

    Maps error codes to URI paths that could link to API documentation.
    This provides machine-readable error type identification following RFC 7807.

    Args:
        error_code: The error code string (e.g., "validation_error")

    Returns:
        URI string for the error type (e.g., "/errors/validation-error")
    """
    # Convert snake_case to kebab-case for URI
    return f"/errors/{error_code.replace('_', '-')}"


def get_error_data(exc, response, context):
    """
    Extract standardized error data from exception.

    Args:
        exc: The exception instance
        response: DRF Response object
        context: Request context dict

    Returns:
        Dict with code, message, and details keys
    """
    # Extract request_id for throttle and other errors that need tracking
    request_id = None
    if context and "request" in context:
        request = context["request"]
        request_id = getattr(request, "id", None)
    # Determine error code based on exception type
    if isinstance(exc, ValidationError):
        error_code = "validation_error"
        error_message = "Invalid input data."
        # Extract field-level validation errors
        details = (
            response.data
            if isinstance(response.data, dict)
            else {"non_field_errors": response.data}
        )

    elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        error_code = "authentication_failed"
        error_message = "Authentication credentials were not provided or are invalid."
        details = None

    elif isinstance(exc, PermissionDenied):
        error_code = "permission_denied"
        error_message = "You do not have permission to perform this action."
        # Include custom permission error details if provided
        details = {"detail": str(exc)} if str(exc) else None

    elif isinstance(exc, NotFound):
        error_code = "not_found"
        error_message = "The requested resource was not found."
        details = {"detail": str(exc)} if str(exc) else None

    elif isinstance(exc, ParseError):
        error_code = "parse_error"
        error_message = "Malformed request data."
        details = {"detail": str(exc)} if str(exc) else None

    elif isinstance(exc, MethodNotAllowed):
        error_code = "method_not_allowed"
        # MethodNotAllowed stores method in detail string, not as attribute
        error_message = str(exc) if str(exc) else "Method not allowed."
        details = None

    elif isinstance(exc, NotAcceptable):
        error_code = "not_acceptable"
        error_message = "Could not satisfy the request Accept header."
        details = None

    elif isinstance(exc, UnsupportedMediaType):
        error_code = "unsupported_media_type"
        # Extract media type from exception detail
        error_message = str(exc) if str(exc) else "Unsupported media type in request."
        details = None

    elif isinstance(exc, Throttled):
        error_code = "throttled"
        error_message = "Request was throttled. Please try again later."
        # Include wait_seconds for client-side retry logic and request_id for tracking
        details = {"wait_seconds": exc.wait if hasattr(exc, "wait") else None}
        if request_id:
            details["request_id"] = request_id

    else:
        # Generic error for other DRF exceptions
        # Try to infer error code from status code or response data
        if response.status_code == 404:
            error_code = "not_found"
            error_message = "The requested resource was not found."
            details = None
        elif isinstance(response.data, dict) and "detail" in response.data:
            detail_str = str(response.data["detail"]).lower()
            if "not found" in detail_str:
                error_code = "not_found"
                error_message = "The requested resource was not found."
                details = None
            else:
                error_code = "error"
                error_message = str(exc) if str(exc) else "An error occurred."
                details = response.data
        else:
            error_code = "error"
            error_message = str(exc) if str(exc) else "An error occurred."
            details = response.data if response.data != error_message else None

    return {
        "code": error_code,
        "message": error_message,
        "details": details,
    }
