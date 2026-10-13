from datetime import timedelta
import time
from django.db import close_old_connections, connections
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from notifications.models import NotificationSend
from notifications.services import safely_dispatch, dispatch, MAX_ATTEMPTS


class Command(BaseCommand):
    help = 'Send pending/failed customer updates; no SMS or email is sent to unverified contacts.'

    def add_arguments(self, parser):
        parser.add_argument('--watch', action='store_true', help='Keep processing the queue as a managed worker.')
        parser.add_argument('--interval', type=int, default=60, help='Seconds between queue checks in watch mode; minimum 10.')
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--retry-now', action='store_true', help='Ignore backoff for pending/failed jobs, preserving attempt limits.')

    def handle(self, *args, **options):
        while True:
            if not connections['default'].in_atomic_block:
                close_old_connections()
            self.run_batch(options)
            if not options['watch']:
                break
            try:
                time.sleep(max(10, options['interval']))
            except KeyboardInterrupt:
                break

    def run_batch(self, options):
        now = timezone.now()
        queryset = NotificationSend.objects.filter(attempts__lt=MAX_ATTEMPTS).filter(Q(status__in=['pending', 'failed']) | Q(status='sending', claimed_at__lt=now-timedelta(minutes=15)))
        if not options['retry_now']:
            queryset = queryset.filter(next_attempt_at__lte=now)
        ids = list(queryset.order_by('pk').values_list('pk', flat=True)[:max(0, options['limit'])])
        sent = 0
        for pk in ids:
            try:
                sent += int(dispatch(pk, retry_now=options['retry_now']))
            except Exception:
                self.stderr.write(f'Job {pk} remains queued for retry.')
        self.stdout.write(f'Checked {len(ids)} queued updates; sent {sent}.')
