from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    # Аутентификация
    path('login/', auth_views.LoginView.as_view(
        template_name='users/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    
    # Используем кастомное представление для выхода
    path('logout/', views.logout_view, name='logout'),
    
    path('register/', views.register, name='register'),
    
    # Профиль пользователя
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
] 