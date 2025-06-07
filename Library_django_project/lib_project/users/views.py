from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from books.models import UserBookRelation
from recommendations.models import UserSurveyProfile

# Create your views here.

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(
                request, 
                'Регистрация успешно завершена! Пожалуйста, пройдите короткий опрос, чтобы мы могли подобрать для вас интересные книги.'
            )
            return redirect('recommendations:survey_step1')
    else:
        form = UserRegistrationForm()
    return render(request, 'users/register.html', {'form': form})

@login_required
def profile(request):
    """Профиль пользователя со статистикой"""
    # Получаем все книги пользователя
    user_books = UserBookRelation.objects.filter(user=request.user)
    
    # Базовая статистика
    total_books = user_books.count()
    books_read = user_books.filter(list_type='read').count()
    books_reading = user_books.filter(list_type='in_progress').count()
    books_want = user_books.filter(list_type='want').count()
    favorite_books = user_books.filter(list_type='favorite').count()
    
    # Статистика по времени
    last_month = timezone.now() - timedelta(days=30)
    books_added_last_month = user_books.filter(added_at__gte=last_month).count()
    books_read_last_month = user_books.filter(
        list_type='read',
        added_at__gte=last_month
    ).count()
    
    # Средняя скорость чтения (книг в месяц)
    reading_speed = books_read_last_month if books_read_last_month > 0 else 0
    
    # Проверяем наличие результатов опроса
    has_survey = UserSurveyProfile.objects.filter(user=request.user).exists()
    survey_date = None
    if has_survey:
        survey = UserSurveyProfile.objects.get(user=request.user)
        survey_date = survey.updated_at
    
    # Статистика по жанрам
    genre_stats = user_books.filter(
        list_type='read'
    ).values(
        'book__genre'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    context = {
        'total_books': total_books,
        'books_read': books_read,
        'books_reading': books_reading,
        'books_want': books_want,
        'favorite_books': favorite_books,
        'books_added_last_month': books_added_last_month,
        'books_read_last_month': books_read_last_month,
        'reading_speed': reading_speed,
        'has_survey': has_survey,
        'survey_date': survey_date,
        'genre_stats': genre_stats,
    }
    
    return render(request, 'users/profile.html', context)

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
    # Очищаем все сообщения перед выходом
    storage = messages.get_messages(request)
    storage.used = True
    
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('home')
