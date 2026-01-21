# Ingestion Guardrails

Goal:
Harden CSV ingestion without changing product scope.

Steps:
1. Identify the current CSV schema and required fields.
2. Add strict validation with clear error messages.
3. Add ingest lifecycle states: received, validated, parsed, processed, failed.
4. Add tests for:
   - Missing columns
   - Wrong data types
   - Empty rows
   - Bad dates
   - Partial files
5. Ensure reruns remain idempotent and safe.
6. Update or create documentation for the CSV contract.
