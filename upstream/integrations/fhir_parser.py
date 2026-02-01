"""
FHIR ExplanationOfBenefit Resource Parser.

Parses FHIR R4 ExplanationOfBenefit (EOB) resources into ClaimRecord format
with proper field extraction, validation, and patient MRN de-identification.
"""

import hashlib
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FHIRParseError(Exception):
    """Exception raised when FHIR resource parsing fails."""
    pass


class FHIRParser:
    """
    Parser for FHIR R4 resources.

    Extracts claim data from ExplanationOfBenefit resources:
    - Patient MRN (de-identified using hash)
    - Claim amounts (billed, allowed, paid)
    - Dates (service, decision)
    - Payer information
    - CPT codes and modifiers
    - Diagnosis codes
    """

    REQUIRED_FIELDS = ["resourceType", "id", "patient", "insurer"]

    def __init__(self, customer_salt: str = ""):
        """
        Initialize parser.

        Args:
            customer_salt: Salt for patient MRN hashing (customer-specific)
        """
        self.customer_salt = customer_salt

    def parse_eob(self, eob: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse FHIR ExplanationOfBenefit resource into ClaimRecord format.

        Args:
            eob: FHIR R4 ExplanationOfBenefit resource

        Returns:
            Dict with ClaimRecord-compatible fields

        Raises:
            FHIRParseError: If required fields are missing or invalid
        """
        self._validate_resource_type(eob, "ExplanationOfBenefit")
        self._validate_required_fields(eob)

        # Extract core identifiers
        resource_id = eob.get("id")
        patient_reference = self._extract_reference(eob.get("patient", {}))
        patient_mrn_hash = self._hash_patient_mrn(patient_reference)

        # Extract payer information
        payer = self._extract_payer(eob)

        # Extract dates
        dates = self._extract_dates(eob)

        # Extract financial information
        financials = self._extract_financials(eob)

        # Extract CPT codes, modifiers, and diagnoses
        procedures = self._extract_procedures(eob)
        diagnoses = self._extract_diagnoses(eob)

        # Determine outcome
        outcome = self._extract_outcome(eob)

        # Build ClaimRecord-compatible result
        result = {
            "source_id": resource_id,
            "patient_mrn_hash": patient_mrn_hash,
            "payer": payer,
            "cpt": procedures.get("primary_cpt", ""),
            "modifier_codes": procedures.get("modifiers", []),
            "diagnosis_codes": diagnoses,
            "procedure_count": procedures.get("procedure_count", 1),
            "submitted_date": dates.get("submitted_date"),
            "decided_date": dates.get("decided_date"),
            "payment_date": dates.get("payment_date"),
            "outcome": outcome,
            "billed_amount": financials.get("billed_amount"),
            "allowed_amount": financials.get("allowed_amount"),
            "paid_amount": financials.get("paid_amount"),
            "submitted_via": "ehr_webhook",
            "source_data_hash": self._compute_source_hash(eob),
        }

        logger.debug(
            f"Parsed EOB {resource_id}: payer={payer}, cpt={result['cpt']}, "
            f"outcome={outcome}"
        )

        return result

    def parse_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse FHIR R4 Claim resource into ClaimRecord format.

        Similar to EOB but for pre-adjudication claims.

        Args:
            claim: FHIR R4 Claim resource

        Returns:
            Dict with ClaimRecord-compatible fields
        """
        self._validate_resource_type(claim, "Claim")

        resource_id = claim.get("id")
        patient_reference = self._extract_reference(claim.get("patient", {}))
        patient_mrn_hash = self._hash_patient_mrn(patient_reference)

        # Extract payer from insurer
        payer = "Unknown"
        insurer = claim.get("insurer", {})
        if isinstance(insurer, dict):
            payer = insurer.get("display", insurer.get("reference", "Unknown"))

        # Extract dates from billablePeriod
        billable_period = claim.get("billablePeriod", {})
        submitted_date = self._parse_date(billable_period.get("start"))
        decided_date = self._parse_date(billable_period.get("end"))

        # Extract items and CPT codes
        items = claim.get("item", [])
        cpt_codes = []
        modifiers = []
        total_amount = Decimal("0.00")

        for item in items:
            # Extract CPT code
            product = item.get("productOrService", {})
            codings = product.get("coding", [])
            for coding in codings:
                code = coding.get("code")
                if code:
                    cpt_codes.append(code)

            # Extract modifiers
            item_modifiers = item.get("modifier", [])
            for mod in item_modifiers:
                mod_codings = mod.get("coding", [])
                for mc in mod_codings:
                    if mc.get("code"):
                        modifiers.append(mc.get("code"))

            # Extract amount
            unit_price = item.get("unitPrice", {})
            if unit_price.get("value"):
                total_amount += Decimal(str(unit_price.get("value")))

        result = {
            "source_id": resource_id,
            "patient_mrn_hash": patient_mrn_hash,
            "payer": payer,
            "cpt": cpt_codes[0] if cpt_codes else "",
            "modifier_codes": list(set(modifiers)),
            "diagnosis_codes": self._extract_diagnoses(claim),
            "procedure_count": len(cpt_codes) or 1,
            "submitted_date": submitted_date,
            "decided_date": decided_date or submitted_date,
            "payment_date": None,
            "outcome": "OTHER",  # Claim not yet adjudicated
            "billed_amount": total_amount if total_amount else None,
            "allowed_amount": None,
            "paid_amount": None,
            "submitted_via": "ehr_webhook",
            "source_data_hash": self._compute_source_hash(claim),
        }

        return result

    def _validate_resource_type(self, resource: Dict[str, Any], expected: str):
        """Validate FHIR resourceType matches expected."""
        resource_type = resource.get("resourceType")
        if resource_type != expected:
            raise FHIRParseError(
                f"Invalid resourceType: expected '{expected}', got '{resource_type}'"
            )

    def _validate_required_fields(self, resource: Dict[str, Any]):
        """Validate required fields are present."""
        missing = []
        for field in self.REQUIRED_FIELDS:
            if not resource.get(field):
                missing.append(field)
        if missing:
            raise FHIRParseError(f"Missing required fields: {', '.join(missing)}")

    def _extract_reference(self, reference_obj: Dict[str, Any]) -> str:
        """Extract reference ID from FHIR Reference type."""
        if isinstance(reference_obj, str):
            return reference_obj
        return reference_obj.get("reference", "") or reference_obj.get("id", "")

    def _hash_patient_mrn(self, patient_reference: str) -> str:
        """
        De-identify patient MRN using SHA-256 hash.

        Args:
            patient_reference: Patient reference string (e.g., "Patient/12345")

        Returns:
            SHA-256 hash of the MRN with customer salt
        """
        # Extract ID from reference format "Patient/12345"
        mrn = patient_reference
        if "/" in patient_reference:
            mrn = patient_reference.split("/")[-1]

        # Hash with customer-specific salt
        data = f"{self.customer_salt}:{mrn}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def _extract_payer(self, eob: Dict[str, Any]) -> str:
        """Extract payer name from EOB insurer field."""
        insurer = eob.get("insurer", {})
        if isinstance(insurer, dict):
            # Try display name first, then reference
            display = insurer.get("display")
            if display:
                return display
            reference = insurer.get("reference", "")
            if reference:
                return reference.split("/")[-1]
        return "Unknown"

    def _extract_dates(self, eob: Dict[str, Any]) -> Dict[str, Optional[date]]:
        """Extract relevant dates from EOB."""
        dates = {
            "submitted_date": None,
            "decided_date": None,
            "payment_date": None,
        }

        # Try billablePeriod for service dates
        billable_period = eob.get("billablePeriod", {})
        if billable_period:
            dates["submitted_date"] = self._parse_date(billable_period.get("start"))
            dates["decided_date"] = self._parse_date(billable_period.get("end"))

        # Try created date as fallback for submitted
        if not dates["submitted_date"]:
            dates["submitted_date"] = self._parse_date(eob.get("created"))

        # Payment info
        payment = eob.get("payment", {})
        if payment:
            dates["payment_date"] = self._parse_date(payment.get("date"))

        # Ensure we have valid dates
        if not dates["submitted_date"]:
            dates["submitted_date"] = date.today()
        if not dates["decided_date"]:
            dates["decided_date"] = dates["submitted_date"]

        return dates

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse FHIR date string to Python date."""
        if not date_str:
            return None
        try:
            # FHIR dates can be YYYY, YYYY-MM, or YYYY-MM-DD
            if len(date_str) == 4:
                return date(int(date_str), 1, 1)
            elif len(date_str) == 7:
                return datetime.strptime(date_str, "%Y-%m").date()
            elif len(date_str) >= 10:
                return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None

    def _extract_financials(self, eob: Dict[str, Any]) -> Dict[str, Optional[Decimal]]:
        """Extract financial amounts from EOB."""
        financials = {
            "billed_amount": None,
            "allowed_amount": None,
            "paid_amount": None,
        }

        # Try total array
        totals = eob.get("total", [])
        for total in totals:
            category = total.get("category", {})
            code = self._get_coding_code(category)
            amount = self._extract_money(total.get("amount", {}))

            if code == "submitted" or code == "billableCost":
                financials["billed_amount"] = amount
            elif code == "eligible" or code == "allowed":
                financials["allowed_amount"] = amount
            elif code == "paymentAmount" or code == "benefit":
                financials["paid_amount"] = amount

        # Fallback to payment.amount
        if not financials["paid_amount"]:
            payment = eob.get("payment", {})
            if payment:
                financials["paid_amount"] = self._extract_money(payment.get("amount", {}))

        return financials

    def _extract_money(self, money: Dict[str, Any]) -> Optional[Decimal]:
        """Extract Decimal from FHIR Money type."""
        if not money:
            return None
        value = money.get("value")
        if value is not None:
            return Decimal(str(value))
        return None

    def _get_coding_code(self, codeable_concept: Dict[str, Any]) -> Optional[str]:
        """Get first code from CodeableConcept."""
        codings = codeable_concept.get("coding", [])
        if codings and len(codings) > 0:
            return codings[0].get("code")
        return None

    def _extract_procedures(self, eob: Dict[str, Any]) -> Dict[str, Any]:
        """Extract CPT codes and modifiers from EOB items."""
        items = eob.get("item", [])
        cpt_codes = []
        modifiers = []

        for item in items:
            # Extract CPT code from productOrService
            product = item.get("productOrService", {})
            codings = product.get("coding", [])
            for coding in codings:
                code = coding.get("code")
                system = coding.get("system", "")
                # Look for CPT codes (HCPCS, CPT systems)
                if code and ("cpt" in system.lower() or "hcpcs" in system.lower() or not system):
                    cpt_codes.append(code)

            # Extract modifiers
            item_modifiers = item.get("modifier", [])
            for mod in item_modifiers:
                mod_codings = mod.get("coding", [])
                for mc in mod_codings:
                    if mc.get("code"):
                        modifiers.append(mc.get("code"))

        return {
            "primary_cpt": cpt_codes[0] if cpt_codes else "",
            "all_cpt_codes": list(set(cpt_codes)),
            "modifiers": list(set(modifiers)),
            "procedure_count": max(len(cpt_codes), 1),
        }

    def _extract_diagnoses(self, resource: Dict[str, Any]) -> List[str]:
        """Extract diagnosis codes from FHIR resource."""
        diagnosis_codes = []

        # Try diagnosis array (standard in EOB/Claim)
        diagnoses = resource.get("diagnosis", [])
        for diag in diagnoses:
            diag_codeable = diag.get("diagnosisCodeableConcept", {})
            codings = diag_codeable.get("coding", [])
            for coding in codings:
                code = coding.get("code")
                if code:
                    diagnosis_codes.append(code)

        return list(set(diagnosis_codes))

    def _extract_outcome(self, eob: Dict[str, Any]) -> str:
        """Extract claim outcome from EOB."""
        outcome_map = {
            "complete": "PAID",
            "partial": "PAID",
            "queued": "OTHER",
            "error": "DENIED",
            "entered-in-error": "OTHER",
        }

        outcome = eob.get("outcome", "").lower()
        if outcome in outcome_map:
            return outcome_map[outcome]

        # Check disposition or adjudication
        disposition = eob.get("disposition", "").lower()
        if "denied" in disposition or "reject" in disposition:
            return "DENIED"
        if "approved" in disposition or "paid" in disposition:
            return "PAID"

        # Check if there's a payment amount (implies paid)
        payment = eob.get("payment", {})
        if payment and payment.get("amount", {}).get("value"):
            return "PAID"

        return "OTHER"

    def _compute_source_hash(self, resource: Dict[str, Any]) -> str:
        """Compute hash of source resource for deduplication."""
        import json
        # Use canonical JSON representation for consistent hashing
        canonical = json.dumps(resource, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_eob(eob: Dict[str, Any], customer_salt: str = "") -> Dict[str, Any]:
    """
    Convenience function to parse EOB resource.

    Args:
        eob: FHIR R4 ExplanationOfBenefit resource
        customer_salt: Salt for patient MRN hashing

    Returns:
        Dict with ClaimRecord-compatible fields
    """
    parser = FHIRParser(customer_salt=customer_salt)
    return parser.parse_eob(eob)


def parse_claim(claim: Dict[str, Any], customer_salt: str = "") -> Dict[str, Any]:
    """
    Convenience function to parse Claim resource.

    Args:
        claim: FHIR R4 Claim resource
        customer_salt: Salt for patient MRN hashing

    Returns:
        Dict with ClaimRecord-compatible fields
    """
    parser = FHIRParser(customer_salt=customer_salt)
    return parser.parse_claim(claim)
