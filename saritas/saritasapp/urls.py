from django.urls import path, register_converter
from core.converters import EncryptedIDConverter
from . import views
from .views import receipt_detail, update_receipt, generate_receipt_pdf
from django.contrib.auth import views as auth_views
from .views import render, made_to_order_view, staff_sign_up

app_name = 'saritasapp'


register_converter(EncryptedIDConverter, 'encrypted')

urlpatterns = [
    path('add-inventory/', views.add_inventory, name='add_inventory'),
    path('inventory/', views.inventory_view, name='inventory_list'),
    path('add-category/', views.add_category, name='add_category'),
    path('add_color/', views.add_color, name='add_color'),
    path('add_size/', views.add_size, name='add_size'),
    path('inventory/<str:encrypted_id>/', views.view_item, name='view_inventory'),
    path('inventory/<str:encrypted_id>/edit/', views.edit_inventory, name='edit_inventory'),
    path('inventory/<str:encrypted_id>/delete/', views.delete_inventory, name='delete_inventory'),
    
    path("customer/list/", views.customer_list, name="customer_list"),
    path('customers/<str:encrypted_id>/', views.view_customer, name='view_customer'),

    path('rental/return/<str:encrypted_id>/', views.return_rental, name='return_rental'),
    path('manage-staff/', views.manage_staff, name='manage_staff'),
    path('manage-staff/edit/<int:staff_id>/', views.edit_staff, name='edit_staff'),
    path('manage-staff/delete/<int:staff_id>/', views.delete_staff, name='delete_staff'),

    # Data analysis
    path('data-analysis/', views.data_analysis, name='data_analysis'),

    # Calendar
    path("calendar/", views.calendar_view, name="calendar"),
    path("ongoing-events/", views.ongoing_events, name="ongoing_events"),
    path("upcoming-events/", views.upcoming_events, name="upcoming_events"),
    path("past-events/", views.past_events, name="past_events"),
    path("create-event/", views.create_event, name="create_event"),
    path("view-event/<str:encrypted_id>/", views.view_event, name="view_event"),
    path("api/events/", views.get_events, name="api_events"),
    path('event/<str:encrypted_id>/edit/', views.edit_event, name='edit_event'),
    path('event/<str:encrypted_id>/delete/', views.delete_event, name='delete_event'),
    path('api/rentals/', views.rental_events_api, name='api_rentals'),


    # Made-to-order & Receipts
    path("made_to_order/", made_to_order_view, name="made_to_order"),
    path('receipt/', views.receipt_view, name='receipt'),
    path('receipt/<str:id>/', views.receipt_detail, name='receipt-detail'),
    path('receipt/<str:id>/update/', views.update_receipt, name='receipt-update'),
    path('receipt/<str:id>/pdf/', views.generate_receipt_pdf, name='receipt-pdf'),

    # Login and Signup
    path("signup/", views.staff_sign_up, name="signup"),
    path("admin-signup/", views.admin_signup, name="admin_signup"),
    path("login/", views.sign_in, name="sign_in"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),

    # Profile
    path("staff-profile/", views.staff_profile_view, name="staff_profile"),
    path("logout_page/", lambda request: render(request, "saritasapp/logout.html"), name="logout_page"),

    # Rentals
    path('rental-tracker/', views.rental_tracker, name='rental_tracker'),
    path('rentals/approvals/', views.rental_approvals, name='rental_approvals'),
    path('rentals/approvals/<str:encrypted_id>/<str:action>/', views.approve_or_reject_rental, name='approve_or_reject_rental'),
    path('rental/<str:encrypted_id>/', views.rental_detail, name='rental_detail'),

    # Reservations
    path('reservations/', views.view_reservations, name='view_reservations'),
    path('reservations/<str:encrypted_id>/<str:action>/', views.update_reservation, name='update_reservation'),

    # Packages
    path('wedding-packages/', views.wedding_packages, name='wedding_packages'),
    path('wedding-confirmation/', views.wedding_confirmation, name='wedding_confirmation'),
    path('debut-packages/', views.debut_packages, name='debut_packages'),
    path('additional-services/', views.additional_services, name='additional_services'),
    path('debut-confirmation/', views.debut_confirmation, name='debut_confirmation'),
    path('additional-confirmation/', views.additional_confirmation, name='additional_confirmation'),

    path('wardrobe-packages/', views.WardrobePackageListView.as_view(), name='wardrobe_package_list'),
    path('wardrobe-packages/create/', views.WardrobePackageCreateView.as_view(), name='wardrobe_package_create'),
    path('wardrobe-packages/<str:encrypted_id>/', views.WardrobePackageDetailView.as_view(), name='wardrobe_package_detail'),
    path('wardrobe-packages/<str:encrypted_id>/update/', views.WardrobePackageUpdateView.as_view(), name='wardrobe_package_update'),
    path('wardrobe-packages/<str:encrypted_id>/delete/', views.WardrobePackageDeleteView.as_view(),name='delete_package'),
    path('wardrobe-packages/<str:package_id>/items/<str:item_id>/edit/', views.EditPackageItemView.as_view(), name='edit_package_item'),
    path('wardrobe-packages/<str:encrypted_id>/add-item/', views.AddPackageItemView.as_view(),name='add_package_item'),
    path('wardrobe-packages/<str:package_id>/items/<str:item_id>/edit/', views.EditPackageItemView.as_view(), name='edit_package_item'),
    path('wardrobe-packages/<str:encrypted_id>/add-item/submit/', views.AddPackageItemSubmitView.as_view(), name='submit_package_item'),
    path('wardrobe-packages/<str:encrypted_id>/add-items/bulk/', views.SubmitBulkPackageItemsView.as_view(), name='submit_bulk_package_items'),
    path('package-approvals/', views.package_rental_approvals, name='package_rental_approvals'),
    path('package-approvals/<str:encrypted_id>/<str:action>/', views.update_package_rental_status, name='update_package_rental_status'),
    path('package-rentals/<str:encrypted_id>/', views.package_rental_detail, name='package_rental_detail'),
    path('filter-inventory-items/', views.FilterInventoryItemsView.as_view(), name='filter_inventory_items'),
]
