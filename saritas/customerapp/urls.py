from django.urls import path
from . import views

app_name = 'customerapp'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('register/', views.register, name='register'),
    path('profile/', views.customer_profile, name='customer_profile'),
    path('profile/edit/', views.edit_customer_profile, name='edit_profile'),
    path('dashboard/', views.customer_dashboard, name='dashboard'),
    path('wardrobe/', views.wardrobe_view, name='wardrobe'),
    path('wardrobe/<int:item_id>/', views.item_detail, name='item_detail'),
    path('rent-item/<int:inventory_id>/', views.rent_item, name='rent_item'),
    path('reservation/<int:item_id>/', views.reserve_item, name='reservation'),
    path('rentals/', views.rental_list, name='rental_list'),
    path('my-rentals/', views.my_rentals, name='my_rentals'),
    path('rental/<int:rental_id>/', views.rental_detail, name='rental_detail'),
    path('logout/', views.logout_view, name='logout'),
    path('story/',views.about_us, name='about_us'),
    path('clear-welcome/', views.clear_welcome_message, name='clear_welcome_message'),
    path('package/',views.package_detail, name='package_detail' ),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-as-read/<int:notification_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('notifications/mark-all-as-read/', views.mark_all_notifications_as_read, name='mark_all_notifications_as_read'),
    path('packages/', views.CustomerPackageListView.as_view(), name='package_list'),
    path('packages/<int:pk>/', views.CustomerPackageDetailView.as_view(), name='package_detail'),
    path('packages/<int:pk>/rent/', views.CreateRentalView.as_view(), name='create_rental'),
    path('packages/<int:package_id>/rent/', views.rent_package, name='rent_package'),
    path('package-rentals/<int:rental_id>/', views.package_rental_detail, name='package_rental_detail'),
    path('my-package-rentals/', views.my_package_rentals, name='my_package_rentals'),
    path('packages/<int:package_id>/rent/', views.rent_package, name='rent_package'),
]

