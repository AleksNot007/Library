from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from books.admin import admin_site
from .models import User, ModeratorMessage

User = get_user_model()

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email')

@admin.register(ModeratorMessage)
class ModeratorMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'message_type', 'book', 'created_at', 'is_read')
    list_filter = ('message_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'message', 'book__title')
    raw_id_fields = ('user', 'book')
    date_hierarchy = 'created_at'

# Регистрируем User в нашем кастомном admin_site
admin_site.register(User, CustomUserAdmin)
 