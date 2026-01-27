"""
EHR Webhook Receivers for Upstream Platform.

Accepts FHIR R4 formatted data from EHR systems (Epic, Cerner, athenahealth)
and queues async processing with autonomous rules evaluation.
"""

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def ehr_webhook(request, provider):
    """
    EHR webhook receiver for FHIR R4 claim notifications.

    Accepts claim data from EHR systems (Epic, Cerner, athenahealth) and
    triggers async processing with risk scoring and rules evaluation.

    Authentication:
        Requires X-API-Key header with customer API key.

    Expected payload format (FHIR R4 Claim resource):
    {
      "resourceType": "Claim",
      "patient": {"reference": "Patient/123"},
      "provider": {"reference": "Organization/456"},
      "billablePeriod": {"start": "2024-01-01", "end": "2024-01-31"},
      "item": [
        {
          "productOrService": {"coding": [{"code": "97153"}]},
          "unitPrice": {"value": 150.00}
        }
      ],
      "insurance": [{"coverage": {"display": "Blue Cross"}}]
    }

    Returns:
        - 202 Accepted: Claim queued for async processing
        - 400 Bad Request: Invalid FHIR format
        - 401 Unauthorized: Invalid or missing API key
        - 500 Internal Server Error: Processing failure
    """
    try:
        # Authenticate via API key
        api_key = request.headers.get("X-API-Key") or request.headers.get("X-Api-Key")

        if not api_key:
            logger.warning("EHR webhook request missing X-API-Key header")
            return JsonResponse(
                {"error": "Missing X-API-Key header"}, status=401
            )

        # Authenticate customer
        # TODO: Replace with proper API key model field + secure token generation
        # For Week 1: Use customer name as API key (basic auth)
        from upstream.models import Customer

        try:
            customer = Customer.objects.get(name=api_key)
        except Customer.DoesNotExist:
            logger.warning(f"EHR webhook invalid API key: {api_key}")
            return JsonResponse(
                {"error": "Invalid API key"}, status=401
            )

        # Parse FHIR R4 payload
        payload = json.loads(request.body.decode("utf-8"))

        # Validate FHIR structure
        if payload.get("resourceType") != "Claim":
            return JsonResponse(
                {"error": 'Invalid resourceType. Expected "Claim"'}, status=400
            )

        # Queue async processing
        from upstream.tasks import process_claim_with_automation

        task = process_claim_with_automation.delay(
            customer_id=customer.id, fhir_payload=payload, source="ehr_webhook"
        )

        logger.info(
            f"EHR webhook claim queued for processing: task_id={task.id}, "
            f"customer={customer.id}"
        )

        return JsonResponse(
            {
                "status": "accepted",
                "task_id": str(task.id),
                "message": "Claim queued for processing",
            },
            status=202,
        )

    except json.JSONDecodeError:
        logger.error("EHR webhook received invalid JSON")
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except Exception as e:
        logger.error(f"EHR webhook processing error: {str(e)}")
        return JsonResponse({"error": "Internal processing error"}, status=500)
