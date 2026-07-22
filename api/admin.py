from django.contrib import admin
from .models import UserProfile, Interest


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'instagram_handle', 'is_online', 'latitude', 'longitude')
    search_fields = ('display_name', 'user__email', 'instagram_handle')
    list_filter = ('is_online',)
