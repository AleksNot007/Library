from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from .models import UserSurveyProfile, Book, Author, Language, UserGenrePreference
from .utils import save_survey_results, get_book_recommendations, seed_books
import logging

logger = logging.getLogger(__name__)

@login_required
def survey_redirect(request):
    """Редирект на первый шаг опроса"""
    return redirect('recommendations:survey_step1')

@login_required
def survey_step1(request):
    """Шаг 1: Выбор предпочитаемых жанров"""
    context = {
        'step': 1,
        'genres': Book.GENRE_CHOICES,
    }
    return render(request, 'recommendations/survey_step1.html', context)

@login_required
def survey_step2(request):
    """Шаг 2: Выбор нежелательных жанров"""
    context = {
        'step': 2,
        'genres': Book.GENRE_CHOICES,
    }
    return render(request, 'recommendations/survey_step2.html', context)

@login_required
def survey_step3(request):
    """Шаг 3: Выбор цели чтения"""
    context = {
        'step': 3,
        'reading_goals': UserSurveyProfile.READING_GOAL_CHOICES,
    }
    return render(request, 'recommendations/survey_step3.html', context)

@login_required
def survey_step4(request):
    """Шаг 4: Частота чтения"""
    context = {
        'step': 4,
        'reading_frequencies': UserSurveyProfile.READING_FREQUENCY_CHOICES,
    }
    return render(request, 'recommendations/survey_step4.html', context)

@login_required
def survey_step5(request):
    """Шаг 5: Выбор любимых авторов"""
    context = {
        'step': 5,
        'authors': Author.objects.all().order_by('name'),
    }
    return render(request, 'recommendations/survey_step5.html', context)

@login_required
def survey_step6(request):
    """Шаг 6: Выбор любимых книг"""
    # Получаем выбранные жанры пользователя
    preferred_genres = UserGenrePreference.objects.filter(
        user=request.user,
        weight__gt=0
    ).values_list('genre', flat=True)

    # Получаем книги выбранных жанров
    genre_books = Book.objects.filter(genre__in=preferred_genres)[:10]

    # Получаем популярные книги выбранных авторов
    favorite_authors = request.session.get('favorite_authors', [])
    author_books = Book.objects.filter(authors__in=favorite_authors).order_by('-world_rating')[:10]

    context = {
        'step': 6,
        'genre_books': genre_books,
        'author_books': author_books,
    }
    return render(request, 'recommendations/survey_step6.html', context)

@login_required
@require_http_methods(["POST"])
def save_step1(request):
    """Сохранение предпочитаемых жанров"""
    try:
        logger.info('Processing save_step1 request')
        genres = request.POST.getlist('preferred_genres')
        logger.info(f'Received genres: {genres}')
        
        if not genres:
            logger.warning('No genres selected')
            raise ValidationError('Выберите хотя бы один жанр')
        if len(genres) > 5:
            logger.warning(f'Too many genres selected: {len(genres)}')
            raise ValidationError('Можно выбрать не более 5 жанров')

        # Сохраняем в сессию для последующего использования
        request.session['preferred_genres'] = genres
        logger.info('Saved genres to session')
        
        # Сохраняем в базу данных
        UserGenrePreference.objects.filter(user=request.user, weight__gt=0).delete()
        for genre in genres:
            UserGenrePreference.objects.create(
                user=request.user,
                genre=genre,
                weight=1
            )
        logger.info('Saved genres to database')
        
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f'Error in save_step1: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def save_step2(request):
    """Сохранение нежелательных жанров"""
    try:
        genres = request.POST.getlist('banned_genres')
        if not genres:
            raise ValidationError('Выберите хотя бы один жанр')

        # Сохраняем в сессию
        request.session['banned_genres'] = genres
        
        # Сохраняем в базу данных
        UserGenrePreference.objects.filter(user=request.user, weight__lt=0).delete()
        for genre in genres:
            UserGenrePreference.objects.create(
                user=request.user,
                genre=genre,
                weight=-1
            )
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def save_step3(request):
    """Сохранение цели чтения"""
    try:
        reading_goal = request.POST.get('reading_goal')
        if not reading_goal:
            raise ValidationError('Выберите цель чтения')

        # Сохраняем в сессию
        request.session['reading_goal'] = reading_goal
        
        # Обновляем или создаем профиль с временным значением reading_frequency
        profile, created = UserSurveyProfile.objects.get_or_create(
            user=request.user,
            defaults={'reading_frequency': 1.5}  # Временное значение, будет обновлено на шаге 4
        )
        profile.reading_goal = reading_goal
        profile.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def save_step4(request):
    """Сохранение частоты чтения"""
    try:
        reading_frequency = request.POST.get('reading_frequency', '').replace(',', '.')
        if not reading_frequency:
            raise ValidationError('Укажите частоту чтения')

        # Сохраняем в сессию
        request.session['reading_frequency'] = float(reading_frequency)
        
        # Обновляем профиль
        profile, created = UserSurveyProfile.objects.get_or_create(user=request.user)
        profile.reading_frequency = float(reading_frequency)
        profile.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def save_step5(request):
    """Сохранение любимых авторов"""
    try:
        authors = request.POST.getlist('favorite_authors')
        if not authors:
            raise ValidationError('Выберите хотя бы одного автора')

        # Сохраняем в сессию для использования в следующем шаге
        request.session['favorite_authors'] = authors
        
        # Обновляем профиль
        profile, created = UserSurveyProfile.objects.get_or_create(user=request.user)
        profile.fav_authors.set(authors)
        profile.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f'Error in save_step5: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def save_step6(request):
    """Сохранение любимых книг"""
    try:
        books = request.POST.getlist('favorite_books')
        
        # Обновляем профиль пользователя
        profile, created = UserSurveyProfile.objects.get_or_create(user=request.user)
        
        # Добавляем выбранные книги в избранное
        book_objects = Book.objects.filter(id__in=books)
        profile.fav_books.set(book_objects)
        profile.save()
        
        # Очищаем временные данные из сессии
        session_keys = ['preferred_genres', 'banned_genres', 'reading_goal', 
                       'reading_frequency', 'favorite_authors']
        for key in session_keys:
            request.session.pop(key, None)
        
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f'Error in save_step6: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def get_authors(request):
    """API для получения списка авторов"""
    authors = Author.objects.all().values('id', 'name').order_by('name')
    return JsonResponse(list(authors), safe=False)

@login_required
def get_books_by_genres(request):
    """API для получения книг по жанрам"""
    genres = request.GET.getlist('genres')
    books = Book.objects.filter(genre__in=genres).values('id', 'title', 'author__name')
    return JsonResponse(list(books), safe=False)

@login_required
def survey_complete(request):
    """Страница завершения опроса"""
    recommendations = get_book_recommendations(request.user.id)
    return render(request, 'recommendations/survey_complete.html', {
        'recommendations': recommendations
    })

@login_required
def book_autocomplete(request):
    """API для автозаполнения книг"""
    query = request.GET.get('q', '')
    try:
        profile = request.user.survey_profile
        genre_prefs = request.user.survey_genre_preferences.all()
        preferred_genres = [pref.genre for pref in genre_prefs if pref.weight > 0]
        banned_genres = [pref.genre for pref in genre_prefs if pref.weight < 0]
    except UserSurveyProfile.DoesNotExist:
        preferred_genres = []
        banned_genres = []
    
    base_books = seed_books(preferred_genres, banned_genres)
    suggestions = (base_books.filter(title__icontains=query)
                            .values('id', 'title')[:10])
    
    return JsonResponse(list(suggestions), safe=False)

@login_required
def author_autocomplete(request):
    """API для автозаполнения авторов"""
    query = request.GET.get('q', '')
    suggestions = (Author.objects.filter(name__icontains=query)
                               .values('id', 'name')[:10])
    return JsonResponse(list(suggestions), safe=False)
