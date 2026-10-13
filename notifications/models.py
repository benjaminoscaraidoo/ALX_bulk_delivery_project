from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    order = models.ForeignKey('order.Order', on_delete=models.CASCADE)
    event_key = models.CharField(max_length=150, unique=True)
    title = models.CharField(max_length=150)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class NotificationSend(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='sends')
    channel = models.CharField(max_length=10, choices=[('email', 'Email'), ('sms', 'SMS')])
    destination = models.CharField(max_length=254)
    status = models.CharField(max_length=15, default='pending', choices=[('pending', 'Pending'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Skipped')])
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    claimed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=150, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['notification', 'channel'], name='unique_notification_channel')]
