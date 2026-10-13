from django.db import connections, DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute('SELECT 1')
    except DatabaseError:
        return JsonResponse({'status': 'unavailable'}, status=503)
    response = JsonResponse({'status': 'ok'})
    response['Cache-Control'] = 'no-store'
    return response
