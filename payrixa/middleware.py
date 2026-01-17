"""
Custom middleware for Payrixa.
"""
import uuid
import threading
import time
from collections import defaultdict
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

# Thread-local storage for request_id
_request_id_storage = threading.local()


def get_request_id():
    """Get the current request ID from thread-local storage."""
    return getattr(_request_id_storage, 'request_id', None)


def set_request_id(request_id):
    """Set the request ID in thread-local storage."""
    _request_id_storage.request_id = request_id


class RequestIdMiddleware(MiddlewareMixin):
    """
    Middleware to add request ID to each request.
    
    If X-Request-Id header exists, use it. Otherwise, generate a UUID.
    The request_id is attached to request.request_id for access in views.
    """
    
    def process_request(self, request):
        """Add request_id to the request object."""
        request_id = request.META.get('HTTP_X_REQUEST_ID')
        
        if not request_id:
            request_id = str(uuid.uuid4())
        
        request.request_id = request_id
        set_request_id(request_id)
        
        return None
    
    def process_response(self, request, response):
        """Add request_id to response headers."""
        request_id = getattr(request, 'request_id', None)
        if request_id:
            response['X-Request-Id'] = request_id
        
        set_request_id(None)
        
        return response


class SimpleRateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware.
    
    Tracks requests per IP address in memory.
    Not suitable for distributed systems - use Redis-based solution for production.
    """
    
    # In-memory storage: {ip: [(timestamp, path), ...]}
    _request_log = defaultdict(list)
    _cleanup_interval = 60  # Clean up old entries every 60 seconds
    _last_cleanup = time.time()
    
    def process_request(self, request):
        """Check rate limits before processing request."""
        # Skip rate limiting for certain paths
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return None
        
        # Get rate limit settings
        rate_limit_enabled = getattr(settings, 'RATE_LIMIT_ENABLED', True)
        if not rate_limit_enabled:
            return None
        
        max_requests = getattr(settings, 'RATE_LIMIT_MAX_REQUESTS', 100)
        window_seconds = getattr(settings, 'RATE_LIMIT_WINDOW_SECONDS', 60)
        
        # Get client IP
        ip_address = self._get_client_ip(request)
        
        # Clean up old entries periodically
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries(window_seconds)
            SimpleRateLimitMiddleware._last_cleanup = current_time
        
        # Get recent requests for this IP
        recent_requests = [
            (ts, path) for ts, path in self._request_log[ip_address]
            if current_time - ts < window_seconds
        ]
        
        # Check if rate limit exceeded
        if len(recent_requests) >= max_requests:
            response = HttpResponse('Rate limit exceeded. Please try again later.', status=429)
            response['Retry-After'] = str(window_seconds)
            return response
        
        # Log this request
        self._request_log[ip_address] = recent_requests + [(current_time, request.path)]
        
        return None
    
    def _get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
    
    def _cleanup_old_entries(self, window_seconds):
        """Remove old entries from request log."""
        current_time = time.time()
        for ip in list(self._request_log.keys()):
            self._request_log[ip] = [
                (ts, path) for ts, path in self._request_log[ip]
                if current_time - ts < window_seconds
            ]
            if not self._request_log[ip]:
                del self._request_log[ip]
