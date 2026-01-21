# PR Review

Goal:
Review the current changes like a paranoid senior engineer.

Steps:
1. Identify all files changed.
2. Summarize what the change is supposed to do.
3. Identify risk areas.
4. Check ingestion safety: CSV parsing, null handling, type conversion, date parsing.
5. Check alert safety: volume thresholds, confidence logic, suppression windows.
6. Check tests: are new cases covered.
7. Produce a clear review summary with:
   - Must fix items
   - Nice to have improvements
   - Overall risk level
