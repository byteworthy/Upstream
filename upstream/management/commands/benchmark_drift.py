"""
Management command to benchmark drift detection performance.

Usage:
    python manage.py benchmark_drift --customer 1
"""

from django.core.management.base import BaseCommand
from upstream.models import Customer
from upstream.services.payer_drift import detect_drift_events
from datetime import datetime
import time
import tracemalloc


class Command(BaseCommand):
    help = 'Benchmark drift detection performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--customer',
            type=int,
            required=True,
            help='Customer ID to benchmark'
        )
        parser.add_argument(
            '--runs',
            type=int,
            default=3,
            help='Number of benchmark runs (default: 3)'
        )

    def handle(self, *args, **options):
        customer_id = options['customer']
        runs = options['runs']

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Customer {customer_id} does not exist'))
            return

        # Get claim count
        from upstream.models import ClaimRecord
        claim_count = ClaimRecord.objects.filter(customer=customer).count()

        self.stdout.write(self.style.SUCCESS('=== Drift Detection Performance Benchmark ==='))
        self.stdout.write(f'Customer: {customer.name} (ID: {customer_id})')
        self.stdout.write(f'Total claims: {claim_count:,}')
        self.stdout.write(f'Benchmark runs: {runs}\n')

        results = []

        for run in range(1, runs + 1):
            self.stdout.write(f'Run {run}/{runs}... ', ending='')
            
            # Start memory tracking
            tracemalloc.start()
            start_time = time.time()
            
            # Run drift detection
            try:
                drift_events = detect_drift_events(customer)
                
                # Calculate metrics
                end_time = time.time()
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                
                duration = end_time - start_time
                events_count = len(drift_events) if drift_events else 0
                memory_mb = peak / 1024 / 1024
                
                results.append({
                    'duration': duration,
                    'memory_mb': memory_mb,
                    'events': events_count
                })
                
                self.stdout.write(self.style.SUCCESS(
                    f'{duration:.2f}s | {memory_mb:.1f} MB | {events_count} events'
                ))
                
            except Exception as e:
                tracemalloc.stop()
                self.stdout.write(self.style.ERROR(f'FAILED: {str(e)}'))
                continue

        if results:
            # Calculate statistics
            avg_duration = sum(r['duration'] for r in results) / len(results)
            avg_memory = sum(r['memory_mb'] for r in results) / len(results)
            avg_events = sum(r['events'] for r in results) / len(results)
            
            min_duration = min(r['duration'] for r in results)
            max_duration = max(r['duration'] for r in results)
            
            # Calculate throughput
            throughput = claim_count / avg_duration if avg_duration > 0 else 0
            
            self.stdout.write('\n' + '=' * 50)
            self.stdout.write(self.style.SUCCESS('Benchmark Results:'))
            self.stdout.write(f'  Average runtime:  {avg_duration:.2f}s')
            self.stdout.write(f'  Min runtime:      {min_duration:.2f}s')
            self.stdout.write(f'  Max runtime:      {max_duration:.2f}s')
            self.stdout.write(f'  Average memory:   {avg_memory:.1f} MB')
            self.stdout.write(f'  Throughput:       {throughput:,.0f} claims/sec')
            self.stdout.write(f'  Events detected:  {avg_events:.0f} avg')
            self.stdout.write('=' * 50)
            
            # Performance assessment
            if throughput > 10000:
                self.stdout.write(self.style.SUCCESS('✓ Excellent performance'))
            elif throughput > 5000:
                self.stdout.write(self.style.SUCCESS('✓ Good performance'))
            elif throughput > 1000:
                self.stdout.write(self.style.WARNING('⚠ Acceptable performance'))
            else:
                self.stdout.write(self.style.WARNING('⚠ Performance may need optimization'))
