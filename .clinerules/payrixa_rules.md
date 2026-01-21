# Payrixa Project Rules

You are working inside the Payrixa production codebase.

Global priorities:
- This is a healthcare adjacent reliability focused system.
- Correctness and trust matter more than speed.
- Operator clarity matters more than engineering cleverness.

Mandatory behavior:
- Always make the smallest change possible.
- Do not refactor unless explicitly instructed.
- Do not change unrelated code.
- If touching ingestion or alerting logic, always add or update tests.
- If changing user facing output, prioritize clarity over cleverness.
- Never expand scope beyond the current task.

Safety rules:
- Never remove validation or guards to make tests pass.
- Never bypass tests.
- Never weaken idempotency or duplicate protection.
- Never assume input data is clean.

Process rules:
- Explain what you plan to change before changing it.
- List the files you will touch.
- After changes, state exactly how to verify correctness.

Product rules:
- Always think in terms of the operator, not the engineer.
- If a change affects alerts or artifacts, explain the user impact.
