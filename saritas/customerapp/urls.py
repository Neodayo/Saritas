from django.urls import path, register_converter
from core.converters import EncryptedIDConverter
from . import email_verification
from . import views

app_name = 'customerapp'

register_converter(EncryptedIDConverter, 'encrypted')

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('register/', views.register, name='register'),
    path('verify-email/', email_verification.request_email, name='request_email'),
    path('enter-otp/', email_verification.verify_otp, name='verify_otp'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('profile/', views.customer_profile, name='customer_profile'),
    path('profile/edit/', views.edit_customer_profile, name='edit_profile'),
    path('dashboard/', views.customer_dashboard, name='dashboard'),
    path('wardrobe/', views.wardrobe_view, name='wardrobe'),
    
    # Updated URL patterns to use encrypted_id consistently
    path('wardrobe/<str:encrypted_id>/', views.item_detail, name='item_detail'),
    # path('wardrobe/<str:encrypted_id>/', views.product_detail, name='product_detail'),
    path('rent-item/<str:encrypted_id>/', views.rent_item, name='rent_item'),

    path('rentals/', views.rental_list, name='rental_list'),
    path('my-rentals/', views.my_rentals, name='my_rentals'),
    path('my-rentals/<str:encrypted_id>/', views.view_rental_detail, name='view_rental_detail'),
    path('my-rentals/<str:encrypted_id>/edit/', views.edit_rental, name='edit_rental'),
    path('my-rentals/<str:encrypted_id>/cancel/', views.cancel_rental_request, name='cancel_rental_request'),
    path('reserve/<str:encrypted_id>/', views.reserve_item, name='reserve_item'),
    path('wardrobe/<str:encrypted_id>/reserve/', views.reserve_item, name='reserve_item'),
    
    path('logout/', views.logout_view, name='logout'),
    path('story/', views.about_us, name='about_us'),
    path('clear-welcome/', views.clear_welcome_message, name='clear_welcome_message'),
    path('package/<str:encrypted_id>/', views.package_detail, name='package_detail'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-as-read/<str:encrypted_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('notifications/mark-all-as-read/', views.mark_all_notifications_as_read, name='mark_all_notifications_as_read'),
    path('packages/', views.CustomerPackageListView.as_view(), name='package_list'),
    path('packages/<int:id>/', views.CustomerPackageDetailView.as_view(), name='package_detail'),
    path('packages/<int:id>/rent/', views.CreateRentalView.as_view(), name='rent_package'),
    path('package-rentals/<str:rental_id>/', views.package_rental_detail, name='package_rental_detail'),
    path('my-rentals/', views.my_package_rentals, name='my_package_rentals'),
    path('my-package-rentals/', views.my_package_rentals, name='my_package_rentals'),
    path('collections/', views.collections_view, name='collections'),
    path('edit-hero/', views.edit_hero, name='edit_hero'),
    path('api/hero/', views.get_hero_data, name='get_hero_data'),
    path('api/hero/update/', views.update_hero, name='update_hero'),
    path('manage-event-slides/', views.manage_event_slides, name='manage_event_slides'),
     path('delete-event-slide/<int:slide_id>/', views.delete_event_slide, name='delete_event_slide'),
    path('update-featured-collections/', views.update_featured_collections, name='update_featured_collections'),
]