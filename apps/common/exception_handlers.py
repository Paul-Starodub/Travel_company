from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.projects.exceptions import ExternalServiceError


def custom_exception_handler(exc, context):
    if isinstance(exc, ExternalServiceError):
        return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return exception_handler(exc, context)
