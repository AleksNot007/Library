from django.contrib import admin
from .models import User
from books.admin import admin_site

@admin.register(User, site=admin_site)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'date_joined', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)
 