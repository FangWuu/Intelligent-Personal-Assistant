class DisableCSRFForAPI:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setattr(request, '_dont_enforce_csrf_checks', True)
        return self.get_response(request)
    
class LogRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print("Headers:", request.headers)
        print("Session Data:", request.session.items())
        print("User Authenticated:", request.user.is_authenticated)

        response = self.get_response(request)
        return response