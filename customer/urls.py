from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import login_view, register_view,logout_view
from . import views

app_name = "customer"

urlpatterns = [
    #path('', include(router.urls)),
    path('', views.home, name='home'),
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
]