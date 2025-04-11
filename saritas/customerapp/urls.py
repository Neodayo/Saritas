from django.urls import path
from . import views

app_name = 'customerapp'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('dashboard/', views.customer_dashboard, name='dashboard'),
    path('wardrobe/', views.wardrobe_view, name='wardrobe'),
    path('wardrobe/<int:item_id>/', views.item_detail, name='item_detail'),
    path('rent-item/<int:inventory_id>/', views.rent_item, name='rent_item'),
    path('reservation/<int:item_id>/', views.reserve_item, name='reservation'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.homepage, name='homepage'),
    path('story/',views.about_us, name='about_us'),
    path('clear-welcome/', views.clear_welcome_message, name='clear_welcome_message'),
    path('package/',views.package_detail, name='package_detail' ),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-as-read/<int:notification_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('notifications/mark-all-as-read/', views.mark_all_notifications_as_read, name='mark_all_notifications_as_read'),
]
