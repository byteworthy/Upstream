"""
Locust Load Tests for Claims API Endpoints.

Tests the claims list, detail, filtering, and payer summary endpoints
under load.

Target Performance:
- List: <500ms p95 response time
- Detail: <200ms p95 response time
- Filter: <500ms p95 response time
- Error rate: <1%

Usage:
    # Run claims tests only
    locust -f tests/test_claims.py --host http://localhost:8000

    # Run headless for CI
    locust -f tests/test_claims.py --headless -u 50 -r 5 -t 60s \
        --host http://localhost:8000 --csv=claims_results
"""

import logging
import random
import sys
from pathlib import Path

from locust import between, events, task

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from upstream.tests_performance_base import (  # noqa: E402
    AuthenticatedUser,
    config,
)

logger = logging.getLogger(__name__)


# Sample payer names for filtering
PAYER_NAMES = [
    "BlueCross",
    "Aetna",
    "UnitedHealth",
    "Cigna",
    "Humana",
    "Kaiser",
    "Anthem",
    "TestPayer",
]

# Sample CPT codes for searching
CPT_CODES = ["99213", "99214", "99215", "80053", "85025", "87086"]


class ClaimsListUser(AuthenticatedUser):
    """
    Load test user for claims list operations.

    Tests paginated list views with various page sizes and filters.
    """

    wait_time = between(1, 3)

    @task(5)
    def list_claims_paginated(self):
        """
        GET /api/v1/claims/ with pagination.

        Tests the most common operation: paginated list view.
        """
        page = random.randint(1, 10)
        page_size = random.choice([25, 50, 100])

        self.get_with_auth(
            f"/api/v1/claims/?page={page}&page_size={page_size}",
            name="/api/v1/claims/?page=[n]&page_size=[n]",
        )

    @task(3)
    def filter_claims_by_payer(self):
        """
        GET /api/v1/claims/?payer=X

        Tests filtering by payer name.
        """
        payer = random.choice(PAYER_NAMES)
        self.get_with_auth(
            f"/api/v1/claims/?payer={payer}",
            name="/api/v1/claims/?payer=[name]",
        )

    @task(2)
    def search_claims_by_cpt(self):
        """
        GET /api/v1/claims/?search=X

        Tests searching by CPT code.
        """
        cpt = random.choice(CPT_CODES)
        self.get_with_auth(
            f"/api/v1/claims/?search={cpt}",
            name="/api/v1/claims/?search=[cpt]",
        )

    @task(2)
    def filter_claims_by_outcome(self):
        """
        GET /api/v1/claims/?outcome=X

        Tests filtering by claim outcome (PAID/DENIED).
        """
        outcome = random.choice(["PAID", "DENIED"])
        self.get_with_auth(
            f"/api/v1/claims/?outcome={outcome}",
            name="/api/v1/claims/?outcome=[status]",
        )

    @task(1)
    def filter_claims_combined(self):
        """
        GET /api/v1/claims/ with multiple filters.

        Tests complex filtering with multiple parameters.
        """
        payer = random.choice(PAYER_NAMES)
        outcome = random.choice(["PAID", "DENIED"])
        page_size = random.choice([25, 50])

        self.get_with_auth(
            f"/api/v1/claims/?payer={payer}&outcome={outcome}&page_size={page_size}",
            name="/api/v1/claims/?payer&outcome&page_size",
        )


class ClaimsDetailUser(AuthenticatedUser):
    """
    Load test user for claims detail operations.

    Tests individual claim retrieval with various IDs.
    """

    wait_time = between(1, 2)

    @task
    def get_claim_detail(self):
        """
        GET /api/v1/claims/{id}/

        Tests retrieving individual claim records.
        Accepts 404 for non-existent claims.
        """
        claim_id = random.randint(1, 100)
        self.get_with_auth(
            f"/api/v1/claims/{claim_id}/",
            allow_not_found=True,
            name="/api/v1/claims/[id]/",
        )


class ClaimsSummaryUser(AuthenticatedUser):
    """
    Load test user for claims summary operations.

    Tests payer summary aggregation endpoint.
    """

    wait_time = between(2, 4)

    @task
    def get_payer_summary(self):
        """
        GET /api/v1/claims/payer_summary/

        Tests the aggregated payer statistics endpoint.
        This is a heavier query that aggregates across claims.
        """
        self.get_with_auth(
            "/api/v1/claims/payer_summary/",
            name="/api/v1/claims/payer_summary/",
        )


class ClaimsHighLoadUser(AuthenticatedUser):
    """
    High-load test user for claims endpoints.

    Simulates aggressive API usage patterns for stress testing.
    """

    wait_time = between(0.5, 1)  # Faster pacing

    @task(3)
    def rapid_list_requests(self):
        """
        Rapid paginated list requests for stress testing.
        """
        page = random.randint(1, 5)
        self.get_with_auth(
            f"/api/v1/claims/?page={page}&page_size=100",
            name="/api/v1/claims/?page=[n] (stress)",
        )

    @task(2)
    def rapid_filter_requests(self):
        """
        Rapid filtered list requests for stress testing.
        """
        payer = random.choice(PAYER_NAMES)
        self.get_with_auth(
            f"/api/v1/claims/?payer={payer}&page_size=100",
            name="/api/v1/claims/?payer=[name] (stress)",
        )

    @task(1)
    def rapid_summary_requests(self):
        """
        Rapid payer summary requests for stress testing.
        """
        self.get_with_auth(
            "/api/v1/claims/payer_summary/",
            name="/api/v1/claims/payer_summary/ (stress)",
        )


# Event listeners for claims-specific metrics
@events.test_start.add_listener
def on_claims_test_start(environment, **kwargs):
    """Log claims test configuration."""
    logger.info("=" * 60)
    logger.info("Claims API Load Test Starting")
    logger.info(f"List threshold: {config.p95_list_threshold_ms}ms")
    logger.info(f"Detail threshold: {config.p95_detail_threshold_ms}ms")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_claims_test_stop(environment, **kwargs):
    """Log claims test summary."""
    logger.info("=" * 60)
    logger.info("Claims API Load Test Completed")

    stats = environment.stats
    endpoints = [
        "/api/v1/claims/?page=[n]&page_size=[n]",
        "/api/v1/claims/?payer=[name]",
        "/api/v1/claims/[id]/",
        "/api/v1/claims/payer_summary/",
    ]

    for name in endpoints:
        entry = stats.entries.get((name, "GET"))
        if entry and entry.num_requests > 0:
            p95 = entry.get_response_time_percentile(0.95)
            logger.info(
                f"{name}: {entry.num_requests} requests, "
                f"avg {entry.avg_response_time:.0f}ms, "
                f"p95 {p95:.0f}ms, "
                f"failures {entry.num_failures}"
            )

    logger.info("=" * 60)
