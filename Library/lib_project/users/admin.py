from django.contrib import admin
from .models import User

# Register your models here.
@admin.register(User)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('username','date_joined')
 