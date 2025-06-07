from typing import List
from .models import Book, Author

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

def autocomplete_books(query: str, selected_genres: List[str], banned_genres: List[str], limit: int = 10) -> List[dict]:
    """
    Поиск книг для автозаполнения с учетом жанровых предпочтений
    
    Args:
        query: Поисковый запрос пользователя
        selected_genres: Список предпочтительных жанров
        banned_genres: Список нежелательных жанров
        limit: Максимальное количество результатов
    
    Returns:
        Список словарей с id и названиями книг
    """
    base = seed_books(selected_genres, banned_genres)
    return (base.filter(title__icontains=query)
                .values('id', 'title')[:limit])

def get_default_recommendations(selected_genres: List[str], banned_genres: List[str], limit: int = 10) -> List[dict]:
    """
    Получает список рекомендованных книг, если пользователь не ввел поисковый запрос
    
    Args:
        selected_genres: Список предпочтительных жанров
        banned_genres: Список нежелательных жанров
        limit: Максимальное количество результатов
    
    Returns:
        Список словарей с id и названиями популярных книг
    """
    return seed_books(selected_genres, banned_genres, limit).values('id', 'title') 