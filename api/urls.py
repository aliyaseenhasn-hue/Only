from django.urls import path
from . import views # استيراد ملف views الخاص بتطبيق api

urlpatterns = [
    path('login-page/', views.login_screen, name='login-page'),
    path('register/', views.register_screen, name='register-page'),
    path('profile/', views.profile_screen, name='profile-page'),
    path('location-update/', views.update_location, name='location-update'),
    path('logout/', views.logout_view, name='logout'),
    path('radar/', views.radar_dashboard, name='radar-dashboard'),
    path('reset-password/', views.reset_password_screen, name='reset-password-page'),
    path('contacts/', views.contact_history_view, name='contact-history'),
    path('discovery/', views.discovery_screen, name='discovery-page'),
    path('user/<int:user_id>/', views.user_detail_view, name='user-detail'),
    path('delete-account/', views.delete_account, name='delete-account'),
    path('control-panel/', views.admin_dashboard, name='admin-dashboard'),
]
