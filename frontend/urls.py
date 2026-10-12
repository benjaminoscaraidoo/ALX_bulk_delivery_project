from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'frontend'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.SignInView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', views.account, {'kind': 'register'}, name='register'),
    path('password-reset/', views.account, {'kind': 'password-reset'}, name='password-reset'),
    path('profile/', views.profile, name='profile'),
    path('orders/<str:pk>/', views.order_detail, name='order'),
]
