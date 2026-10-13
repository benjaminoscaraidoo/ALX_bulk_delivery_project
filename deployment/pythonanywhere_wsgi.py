"""Copy into the PythonAnywhere Web tab's WSGI file after checking the path."""
import os
import sys

project_path = '/home/benjaminoscaraidoo/ALX_bulk_delivery_project'
if project_path not in sys.path:
    sys.path.insert(0, project_path)

os.environ['DJANGO_ENV'] = 'production'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bulk_delivery_project.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
