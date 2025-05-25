from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm

# Create your views here.

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация успешно завершена!')
            return redirect('/')  # Редирект на главную страницу
    else:
        form = UserRegistrationForm()
    return render(request, 'users/register.html', {'form': form})

@login_required
def profile(request):
    """Отображение профиля пользователя"""
    return render(request, 'users/profile.html', {'user': request.user})

@login_required
def edit_profile(request):
    """Редактирование профиля пользователя"""
    if request.method == 'POST':
        # Здесь будет логика обновления профиля
        messages.success(request, 'Профиль успешно обновлен!')
        return redirect('users:profile')
    return render(request, 'users/edit_profile.html', {'user': request.user})

def logout_view(request):
    """Выход из системы"""
    logout(request)  # Выходим из системы в любом случае
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('/')  # Всегда перенаправляем на главную страницу
