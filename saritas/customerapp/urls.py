from django.urls import path
from . import views

app_name = "customerapp" # This is the namespace for the app

urlpatterns = [
    path('register/', views.customer_signup, name='customer_signup'),
    path('login/', views.customer_login, name='customer_login'),
    path('dashboard/', views.customer_dashboard, name='customer_dashboard'),
]