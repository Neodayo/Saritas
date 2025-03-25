from django.urls import path
from . import views

app_name = 'customerapp'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.customer_dashboard, name='dashboard'),
]
