import time
from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse


class SessionIdleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if 'last_request' in request.session:
                elapsed = time.time() - request.session['last_request']
                if elapsed > settings.SESSION_IDLE_TIMEOUT:
                    del request.session['last_request']
                    logout(request)
                    # Return 401 for AJAX requests instead of redirect
                    if (request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                            or request.content_type == 'application/json'):
                        return JsonResponse(
                            {'status': 'error',
                             'code': 'session_expired',
                             'message': 'Session expired. Please login again.'},
                            status=401
                        )
            request.session['last_request'] = time.time()

            # Tasks overdue past their limit lock the user out until the creator moves the date
            # (task/lock.py). It lives here because this middleware is already on every request.
            if request.user.is_authenticated:
                from task.lock import lock_response
                stopped = lock_response(request)
                if stopped is not None:
                    return stopped

        else:
            if 'last_request' in request.session:
                del request.session['last_request']

        response = self.get_response(request)
        return response


class SessionIdleMiddleware1:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if 'last_request' in request.session:
                elapsed = time.time() - request.session['last_request']
                if elapsed > settings.SESSION_IDLE_TIMEOUT:
                    del request.session['last_request']
                    logout(request)
                    # flushing the complete session is an option as well!
                    # request.session.flush()
            request.session['last_request'] = time.time()

        else:
            if 'last_request' in request.session:
                del request.session['last_request']
        response = self.get_response(request)
        return response

