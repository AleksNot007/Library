from typing import List, Dict, Any
from .models import UserSurveyProfile, UserGenrePreference, Book

def seed_books(selected_genres: List[str], banned_genres: List[str], limit: int = 50) -> List[Book]:
    """
    Создает предварительный список книг на основе жанровых предпочтений
    
    Args:
        selected_genres: Список предпочтительных жанров
        banned_genres: Список нежелательных жанров
        limit: Максимальное количество книг в результате
    
    Returns:
        QuerySet книг, отсортированный по рейтингу
    """
    qs = (Book.objects
              .filter(is_approved=True, world_rating__gte=4.8)
              .exclude(genre__in=banned_genres))
    
    if selected_genres:
        qs = qs.filter(genre__in=selected_genres)
    
    return qs.order_by('-world_rating')[:limit]

def get_user_genre_preferences(user_id: int) -> Dict[str, int]:
    """
    Получает словарь жанровых предпочтений пользователя
    
    Args:
        user_id: ID пользователя
    
    Returns:
        Словарь {жанр: вес}
    """
    preferences = UserGenrePreference.objects.filter(user_id=user_id)
    return {pref.genre: pref.weight for pref in preferences}

def save_survey_results(user_id: int, survey_data: Dict[str, Any]) -> UserSurveyProfile:
    """
    Сохраняет результаты опроса пользователя
    
    Args:
        user_id: ID пользователя
        survey_data: Данные опроса в формате:
            {
                'preferred_genres': List[str],
                'banned_genres': List[str],
                'reading_goal': str,
                'mood_tags': List[str],
                'reading_frequency': float,
                'languages': List[str],
                'favorite_authors': List[int],
                'favorite_books': List[int],
                'content_filters': List[str],
                'other_filters': str
            }
    
    Returns:
        Объект профиля пользователя
    """
    # Создаем или обновляем профиль
    profile, _ = UserSurveyProfile.objects.update_or_create(
        user_id=user_id,
        defaults={
            'reading_goal': survey_data['reading_goal'],
            'reading_frequency': survey_data['reading_frequency'],
            'other_content_filters': survey_data.get('other_filters', '')
        }
    )
    
    # Устанавливаем JSON-поля
    profile.set_mood_tags(survey_data['mood_tags'])
    profile.set_content_filters(survey_data['content_filters'])
    
    # Очищаем и добавляем M2M связи
    profile.original_languages.set(survey_data['languages'])
    profile.fav_authors.set(survey_data.get('favorite_authors', []))
    profile.fav_books.set(survey_data.get('favorite_books', []))
    
    # Обновляем жанровые предпочтения
    UserGenrePreference.objects.filter(user_id=user_id).delete()
    
    # Добавляем предпочтительные жанры
    for genre in survey_data['preferred_genres']:
        UserGenrePreference.objects.create(
            user_id=user_id,
            genre=genre,
            weight=1
        )
    
    # Добавляем нежелательные жанры
    for genre in survey_data['banned_genres']:
        UserGenrePreference.objects.create(
            user_id=user_id,
            genre=genre,
            weight=-1
        )
    
    return profile

def get_book_recommendations(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Получает рекомендации книг для пользователя на основе его профиля
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество рекомендаций
    
    Returns:
        Список рекомендованных книг с их весами
    """
    try:
        profile = UserSurveyProfile.objects.get(user_id=user_id)
    except UserSurveyProfile.DoesNotExist:
        return []
    
    # Получаем жанровые предпочтения
    genre_prefs = get_user_genre_preferences(user_id)
    preferred_genres = [genre for genre, weight in genre_prefs.items() if weight > 0]
    banned_genres = [genre for genre, weight in genre_prefs.items() if weight < 0]
    
    # Получаем базовый список книг
    recommendations = seed_books(preferred_genres, banned_genres, limit * 2)
    
    # Фильтруем по контент-фильтрам (в будущем)
    # TODO: Добавить поля для контент-тегов в модель Book
    
    return recommendations.values('id', 'title', 'world_rating')[:limit] 