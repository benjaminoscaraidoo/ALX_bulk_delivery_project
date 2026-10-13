from django.urls import path
from .views import NotificationListAPIView, NotificationReadAPIView

urlpatterns = [
    path('v1/notifications/', NotificationListAPIView.as_view()),
    path('v1/notifications/<int:pk>/read/', NotificationReadAPIView.as_view()),
]
