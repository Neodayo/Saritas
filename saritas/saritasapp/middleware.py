from django.shortcuts import redirect

class CustomerRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Prevent customers from accessing admin/staff pages
        if request.user.is_authenticated:
            if hasattr(request.user, 'customer_profile') and \
               (request.path.startswith('/admin/') or request.path.startswith('/staff/')):
                return redirect('customerapp:homepage')
        return self.get_response(request)