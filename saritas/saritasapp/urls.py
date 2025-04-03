from django.urls import path
from .import views 
from .views import receipt_detail, update_receipt, generate_receipt_pdf
from django.contrib.auth import views as auth_views
from .views import render, update_receipt, receipt_detail, made_to_order_view, staff_sign_up


app_name = 'saritasapp'

urlpatterns = [
    path('', views.sign_in, name='homepage'),
    path('add-inventory/', views.add_inventory, name='add_inventory'),
    path('inventory/', views.inventory_view, name='inventory_list'),
    path('add-category/', views.add_category, name='add_category'),
    path('add_color/', views.add_color, name='add_color'),
    path('add_size/', views.add_size, name='add_size'),
    path('inventory/<int:item_id>/', views.view_item, name='view_inventory'),
    path('inventory/<int:item_id>/edit/', views.edit_inventory, name='edit_inventory'), 
    path('inventory/<int:item_id>/delete/', views.delete_inventory, name='delete_inventory'),
    path("customer/list/", views.customer_list, name="customer_list"),
    path('customers/<int:customer_id>/', views.view_customer, name='view_customer'),
    path('rental/return/<int:rental_id>/', views.return_rental, name='return_rental'),
    path('manage-staff/', views.manage_staff, name='manage_staff'),
    #data analysis
    path('data-analysis/', views.data_analysis, name='data_analysis'),
    #calendar
    path("calendar/", views.calendar_view, name="calendar"),
    path("ongoing-events/", views.ongoing_events, name="ongoing_events"),
    path("upcoming-events/", views.upcoming_events, name="upcoming_events"),
    path("past-events/", views.past_events, name="past_events"),
    path("create-event/", views.create_event, name="create_event"),
    path("view-event/<int:event_id>/", views.view_event, name="view_event"),
    path("api/events/", views.get_events, name="api_events"),
    path('event/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('event/<int:event_id>/delete/', views.delete_event, name='delete_event'),
    #made to oreders,Receipt
    path("made_to_order/", made_to_order_view, name="made_to_order"),
    path('receipt/', views.receipt_view, name='receipt'),
    path('receipt/<int:receipt_id>/', receipt_detail, name='receipt-detail'),
    path('receipt/<int:receipt_id>/update/', update_receipt, name='receipt-update'),
    path('receipt/<int:receipt_id>/pdf/', generate_receipt_pdf, name='receipt-pdf'),
    #login and signup
    path("signup/", views.staff_sign_up, name="signup"),
    path("admin-signup/", views.admin_signup, name="admin_signup"),
    path("login/", views.sign_in, name="sign_in"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    #profile
    path("profile/", views.profile_view, name="profile"),
    path("logout/", views.sign_out, name="logout"), 
    path("logout_page/", lambda request: render(request, "saritasapp/logout.html"), name="logout_page"),
        # ✅ Logout confirmation
    path('notifications/', views.notification_view, name='notifications'),
    path('rental-tracker/', views.rental_tracker, name='rental_tracker'),
    path('rentals/approvals/', views.rental_approvals, name='rental_approvals'),
    path('rentals/<int:rental_id>/<str:action>/', views.approve_rental, name='approve_rental'),
    path('rentals/approvals/', views.rental_approvals, name='rental_approvals'),
    path('rentals/<int:rental_id>/approve/', views.approve_rental, name='approve_rental'),
    path('reservation/', views.reservation_view, name='reservation'),
    path('reservations/', views.view_reservations, name='view_reservations'),
    path('reservations/<int:reservation_id>/update/<str:action>/', views.update_reservation, name='update_reservation'),
    path('wardrobe-packages/', views.wardrobe_package_list, name='wardrobe_package_list'),
    path('wardrobe-packages/<int:package_id>/', views.wardrobe_package_view, name='wardrobe_package_detail'),
    path('wardrobe-packages/<int:package_id>/', views.wardrobe_package_view, name='wardrobe_package_detail'),
    path('wardrobe-packages/<int:package_id>/select/', views.wardrobe_package_view, name='select_wardrobe_package'),
    #packages
    path('packages/', views.packages, name='packages'),

]
