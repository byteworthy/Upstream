"""
Rules Engine for Autonomous Workflow Execution.

Evaluates pre-approved AutomationRule conditions against incoming events
and executes actions WITHOUT human approval. All executions logged to
ExecutionLog for HIPAA audit compliance.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from upstream.models import AutomationRule, ExecutionLog, Customer

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Event that triggers rule evaluation."""

    event_type: str  # 'claim_submitted', 'authorization_expiring', etc.
    customer_id: int
    payload: Dict[str, Any]
    timestamp: datetime


@dataclass
class Action:
    """Action to execute when rule conditions met."""

    rule: AutomationRule
    event: Event
    action_type: str
    action_params: Dict[str, Any]


@dataclass
class ExecutionResult:
    """Result of action execution."""

    success: bool
    result_type: str  # 'SUCCESS', 'FAILED', 'ESCALATED'
    details: Dict[str, Any]
    execution_time_ms: int


class RulesEngine:
    """
    Rules engine orchestrator.

    Loads active rules, evaluates conditions, executes actions,
    and logs all activity for audit trail.
    """

    def __init__(self, customer: Customer):
        self.customer = customer

    def evaluate_event(self, event: Event) -> List[Action]:
        """
        Evaluate event against all active rules.

        Returns list of actions to execute.
        """
        actions = []

        # Load active rules for this customer and event type
        rules = AutomationRule.objects.filter(
            customer=self.customer,
            is_active=True,
            # TODO: Add trigger_event field match once schema updated
        )

        for rule in rules:
            if self._conditions_met(rule, event):
                actions.append(
                    Action(
                        rule=rule,
                        event=event,
                        action_type=rule.actions.get("type", "unknown"),
                        action_params=rule.actions,
                    )
                )

        return actions

    def execute_actions(self, actions: List[Action]) -> List[ExecutionResult]:
        """
        Execute all actions and log results.

        Each action execution is logged to ExecutionLog for audit trail.
        Errors are escalated if rule.escalate_on_error=True.
        """
        results = []

        for action in actions:
            start_time = datetime.now()

            try:
                # Execute action based on type
                result = self._execute_action(action)
                execution_time_ms = int(
                    (datetime.now() - start_time).total_seconds() * 1000
                )

                # Log successful execution
                ExecutionLog.objects.create(
                    customer=self.customer,
                    rule=action.rule,
                    trigger_event=action.event.payload,
                    action_taken=action.action_type,
                    result="SUCCESS",
                    details=result.details,
                    execution_time_ms=execution_time_ms,
                )

                results.append(result)

            except Exception as e:
                execution_time_ms = int(
                    (datetime.now() - start_time).total_seconds() * 1000
                )

                logger.error(
                    f"Action execution failed: {action.action_type} - {str(e)}"
                )

                # Determine if escalation needed
                # Check for escalate_on_error attribute (new schema) or fall back to True
                escalate_on_error = getattr(action.rule, "escalate_on_error", True)
                if escalate_on_error:
                    result_type = "ESCALATED"
                    self._escalate_to_human(action, e)
                else:
                    result_type = "FAILED"

                # Log failed execution
                ExecutionLog.objects.create(
                    customer=self.customer,
                    rule=action.rule,
                    trigger_event=action.event.payload,
                    action_taken=action.action_type,
                    result=result_type,
                    details={"error": str(e)},
                    execution_time_ms=execution_time_ms,
                )

                results.append(
                    ExecutionResult(
                        success=False,
                        result_type=result_type,
                        details={"error": str(e)},
                        execution_time_ms=execution_time_ms,
                    )
                )

        return results

    def _conditions_met(self, rule: AutomationRule, event: Event) -> bool:
        """
        Evaluate if rule conditions are met for this event.

        Conditions are stored in rule.trigger_conditions JSONField.
        Example: {'risk_score': {'operator': 'gt', 'value': 70}}
        """
        conditions = rule.trigger_conditions

        for key, condition in conditions.items():
            operator = condition.get("operator")
            expected_value = condition.get("value")
            actual_value = event.payload.get(key)

            if not self._compare(actual_value, operator, expected_value):
                return False

        return True

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compare actual value against expected using operator."""
        if operator == "gt":
            return actual > expected
        elif operator == "gte":
            return actual >= expected
        elif operator == "lt":
            return actual < expected
        elif operator == "lte":
            return actual <= expected
        elif operator == "eq":
            return actual == expected
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    def _execute_action(self, action: Action) -> ExecutionResult:
        """
        Execute single action using RPA module for portal interactions.

        Supports:
        - submit_reauth: Submit reauthorization request via payer portal
        - submit_appeal: Submit appeal via payer portal
        - Other action types: Stub implementation
        """
        import time
        from upstream.automation.rpa import (
            get_portal_for_payer,
            ReauthRequest,
            AppealRequest,
        )

        logger.info(f"Executing action: {action.action_type} for rule {action.rule.id}")
        start_time = time.time()

        try:
            if action.action_type == "submit_reauth":
                # Execute reauthorization via RPA
                payer = action.action_params.get("payer", "Unknown")
                portal = get_portal_for_payer(payer)
                portal.login()

                request_data = action.action_params.get("request_data", {})
                request = ReauthRequest(
                    auth_number=request_data.get("auth_number", ""),
                    patient_id=request_data.get("patient_id", ""),
                    payer=payer,
                    service_type=request_data.get("service_type", ""),
                    units_requested=request_data.get("units_requested", 0),
                    utilization_report_url=request_data.get("utilization_report_url"),
                )

                portal_result = portal.submit_reauth_request(request)
                portal.logout()

                return ExecutionResult(
                    success=portal_result.success,
                    result_type="SUCCESS" if portal_result.success else "FAILED",
                    details=portal_result.to_dict(),
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            elif action.action_type == "submit_appeal":
                # Execute appeal via RPA
                payer = action.action_params.get("payer", "Unknown")
                portal = get_portal_for_payer(payer)
                portal.login()

                appeal_data = action.action_params.get("appeal_data", {})
                appeal = AppealRequest(
                    claim_id=appeal_data.get("claim_id", ""),
                    payer=payer,
                    denial_reason=appeal_data.get("denial_reason", ""),
                    appeal_letter=appeal_data.get("appeal_letter", ""),
                    supporting_docs=appeal_data.get("supporting_docs", []),
                )

                portal_result = portal.submit_appeal(appeal)
                portal.logout()

                return ExecutionResult(
                    success=portal_result.success,
                    result_type="SUCCESS" if portal_result.success else "FAILED",
                    details=portal_result.to_dict(),
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            else:
                # Stub for other action types
                return ExecutionResult(
                    success=True,
                    result_type="SUCCESS",
                    details={
                        "message": f"Action {action.action_type} executed (stub)",
                        "rule_id": action.rule.id,
                    },
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

        except Exception as e:
            logger.error(f"RPA execution failed: {str(e)}")
            return ExecutionResult(
                success=False,
                result_type="FAILED",
                details={"error": str(e)},
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

    def _escalate_to_human(self, action: Action, error: Exception):
        """
        Escalate failed action to human operator.

        Creates AlertEvent for human review.
        """
        # Import here to avoid circular dependency
        from upstream.alerts.models import AlertEvent

        AlertEvent.objects.create(
            customer=self.customer,
            alert_type="automation_escalation",
            severity="high",
            title=f"Automation Failed: {action.action_type}",
            description=(
                f"Automated action failed and requires human review.\n\n"
                f"Action: {action.action_type}\n"
                f"Error: {str(error)}\n\n"
                f"Please review the execution log and take manual action."
            ),
            evidence_payload={
                "rule_id": action.rule.id,
                "action_type": action.action_type,
                "error": str(error),
                "trigger_event": action.event.payload,
            },
        )

        logger.error(f"Action escalated: {action.action_type} - {error}")
