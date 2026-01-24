"""
Upstream product line applications.

Each product is an isolated Django app with its own models, services, and templates.
Products do not import each other's models directly. Cross-product insights flow through SystemEvent.
"""
