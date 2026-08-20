from rest_framework.views import exception_handler
from rest_framework.exceptions import PermissionDenied


def crm_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and isinstance(exc, PermissionDenied):
        response.status_code = 404
        response.data = {'detail': 'Not found.'}
    return response