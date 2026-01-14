def get_current_customer(request):
    """
    Get the current customer associated with the logged-in user.

    Args:
        request: Django HttpRequest object

    Returns:
        Customer: The customer associated with the user

    Raises:
        ValueError: If user is not authenticated or doesn't have a profile/customer
    """
    if not request.user.is_authenticated:
        raise ValueError("User is not authenticated")

    if not hasattr(request.user, 'profile'):
        raise ValueError("User does not have a profile")

    if not request.user.profile.customer:
        raise ValueError("User profile is not associated with a customer")

    return request.user.profile.customer
