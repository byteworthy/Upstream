"""
Custom middleware for Payrixa.
"""
import uuid
import threading

from django.utils.deprecation import MiddlewareMixin

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
