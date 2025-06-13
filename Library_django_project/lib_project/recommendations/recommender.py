from typing import List, Dict, Any
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from django.db.models import Count, Avg, Q
from books.models import Book, UserBookRelation
from .models import UserSurveyProfile, UserGenrePreference

class BookRecommender:
    def __init__(self, user_id: int):
        self.user_id = user_id
        
    def _get_user_profile(self) -> Dict[str, Any]:
        """Получает профиль пользователя с предпочтениями"""
        try:
            profile = UserSurveyProfile.objects.get(user_id=self.user_id)
            genre_prefs = {
                pref.genre: pref.weight 
                for pref in UserGenrePreference.objects.filter(user_id=self.user_id)
            }
            return {
                'profile': profile,
                'genre_prefs': genre_prefs,
                'fav_authors': list(profile.fav_authors.values_list('id', flat=True)),
                'fav_books': list(profile.fav_books.values_list('id', flat=True))
            }
        except UserSurveyProfile.DoesNotExist:
            return None

    def _get_user_reading_history(self) -> Dict[str, List[int]]:
        """Получает историю чтения пользователя"""
        relations = UserBookRelation.objects.filter(user_id=self.user_id)
        return {
            'read_books': list(relations.values_list('book_id', flat=True)),
            'liked_books': list(relations.filter(like=True).values_list('book_id', flat=True)),
            'rated_books': list(relations.exclude(rating__isnull=True).values_list('book_id', flat=True))
        }

    def _calculate_content_based_scores(self, books_qs) -> Dict[int, float]:
        """Рассчитывает оценки на основе контента книг"""
        user_profile = self._get_user_profile()
        if not user_profile:
            return {}

        scores = {}
        genre_weights = user_profile['genre_prefs']
        fav_authors = set(user_profile['fav_authors'])

        for book in books_qs:
            score = 0.0
            
            # Жанровый вес
            genre_weight = genre_weights.get(book.genre, 0)
            score += genre_weight * 0.4  # 40% веса
            
            # Вес авторов
            author_ids = set(book.authors.values_list('id', flat=True))
            if author_ids & fav_authors:  # Если есть пересечение с любимыми авторами
                score += 0.3  # 30% веса
            
            # Вес рейтинга
            if book.world_rating:
                score += (book.world_rating / 5.0) * 0.3  # 30% веса
            
            scores[book.id] = score

        return scores

    def _get_similar_books(self, book_ids: List[int], limit: int = 10) -> List[int]:
        """Находит похожие книги на основе жанра и авторов"""
        if not book_ids:
            return []
            
        base_books = Book.objects.filter(id__in=book_ids)
        genres = base_books.values_list('genre', flat=True).distinct()
        authors = base_books.values_list('authors', flat=True).distinct()
        
        similar_books = Book.objects.filter(
            Q(genre__in=genres) | Q(authors__in=authors)
        ).exclude(
            id__in=book_ids
        ).annotate(
            rating_count=Count('reviews'),
            avg_rating=Avg('reviews__rating')
        ).filter(
            rating_count__gte=3,  # Минимум 3 оценки
            avg_rating__gte=4.0   # Минимальный рейтинг 4.0
        ).order_by('-avg_rating', '-rating_count')[:limit]
        
        return list(similar_books.values_list('id', flat=True))

    def get_recommendations(self, limit: int = 10, strategy: str = 'mixed') -> List[Dict[str, Any]]:
        """
        Получает рекомендации книг используя выбранную стратегию
        
        Args:
            limit: Максимальное количество рекомендаций
            strategy: Стратегия рекомендаций ('content', 'similar', 'mixed')
        """
        user_profile = self._get_user_profile()
        if not user_profile:
            return []

        # Получаем базовый набор книг
        base_books = Book.objects.filter(
            is_approved=True,
            world_rating__gte=4.0
        ).exclude(
            genre__in=[genre for genre, weight in user_profile['genre_prefs'].items() if weight < 0]
        ).select_related('submitted_by').prefetch_related('authors')

        # Исключаем уже прочитанные книги
        reading_history = self._get_user_reading_history()
        base_books = base_books.exclude(id__in=reading_history['read_books'])

        if strategy == 'content':
            # Только контентная фильтрация
            scores = self._calculate_content_based_scores(base_books)
            book_ids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)[:limit]
            
        elif strategy == 'similar':
            # Поиск похожих книг на основе понравившихся
            book_ids = self._get_similar_books(reading_history['liked_books'], limit)
            
        else:  # mixed
            # Комбинируем оба подхода
            content_limit = limit // 2
            similar_limit = limit - content_limit
            
            # Получаем рекомендации на основе контента
            scores = self._calculate_content_based_scores(base_books)
            content_ids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)[:content_limit]
            
            # Получаем похожие книги
            similar_ids = self._get_similar_books(reading_history['liked_books'], similar_limit)
            
            # Объединяем результаты
            book_ids = content_ids + [id for id in similar_ids if id not in content_ids][:limit]

        # Получаем полные данные книг
        recommended_books = Book.objects.filter(id__in=book_ids).select_related('submitted_by').prefetch_related('authors')
        
        return list(recommended_books.values('id', 'title', 'world_rating'))

def update_recommendations(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Обновляет рекомендации для пользователя"""
    recommender = BookRecommender(user_id)
    return recommender.get_recommendations(limit=limit) 