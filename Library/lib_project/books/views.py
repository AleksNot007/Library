from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count
from .models import Book, Author, Review, UserBookRelation, Quote

def home(request):
    """Главная страница"""
    return render(request, 'books/home.html')

@user_passes_test(lambda u: u.is_superuser)
def site_statistics(request):
    """Страница статистики (доступна только админам)"""
    User = get_user_model()
    
    stats = {
        # Статистика пользователей
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'staff_users': User.objects.filter(is_staff=True).count(),
        'superusers': User.objects.filter(is_superuser=True).count(),
        'users_with_books': UserBookRelation.objects.values('user').distinct().count(),
        
        # Статистика контента
        'total_books': Book.objects.count(),
        'total_authors': Author.objects.count(),
        'total_reviews': Review.objects.count(),
        'total_quotes': Quote.objects.count(),
        
        # Статистика по спискам книг
        'reading_lists': UserBookRelation.objects.values('list_type').annotate(
            count=Count('id')
        ),
        
        # Топ-5 книг по количеству отзывов
        'top_reviewed_books': Book.objects.annotate(
            reviews_count=Count('reviews')
        ).order_by('-reviews_count')[:5],
        
        # Топ-5 цитируемых книг
        'top_quoted_books': Book.objects.annotate(
            quotes_count=Count('quotes')
        ).order_by('-quotes_count')[:5],
        
        # Статистика активности пользователей
        'users_with_reviews': Review.objects.values('user').distinct().count(),
        'users_with_quotes': Quote.objects.values('user').distinct().count(),
        
        # Средняя активность
        'avg_books_per_user': UserBookRelation.objects.count() / User.objects.count() if User.objects.exists() else 0,
        'avg_reviews_per_user': Review.objects.count() / User.objects.count() if User.objects.exists() else 0,
        'avg_quotes_per_user': Quote.objects.count() / User.objects.count() if User.objects.exists() else 0,
    }
    
    return render(request, 'admin/site_statistics.html', stats)
