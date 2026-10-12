from django.db import OperationalError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    # Busy/locked writes can be retried after rollback; never expose SQL details.
    code = getattr(getattr(exc, '__cause__', None), 'sqlite_errorcode', 0)
    if isinstance(exc, OperationalError) and code and (code & 0xff) in (5, 6):
        return Response({'detail': 'Another update is in progress. Please try again shortly.'},
                        status=503, headers={'Retry-After': '1'})
    return exception_handler(exc, context)
