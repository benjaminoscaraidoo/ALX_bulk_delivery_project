import os

bind = '0.0.0.0:' + os.environ.get('PORT', '8000')
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
timeout = 120
accesslog = '-'
errorlog = '-'
capture_output = True
# Deployment uses the host/container supervisor; no local admin socket is needed.
control_socket_disable = True
