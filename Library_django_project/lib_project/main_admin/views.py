from django.shortcuts import render
from books.models import Book
from django.db.models import Count, Avg

def home(request):
    """Главная страница сайта"""
    # Получаем популярные книги
    popular_books = Book.objects.filter(
        is_approved=True
    ).select_related('submitted_by').prefetch_related('authors').annotate(
        avg_rating=Avg('reviews__rating'),
        num_reads=Count('user_relations')
    ).order_by('-num_reads', '-avg_rating')[:4]
    
    # Получаем рекомендации для авторизованного пользователя
    recommended_books = []
    if request.user.is_authenticated:
        # Здесь будет логика рекомендаций
        # Пока просто берем последние добавленные книги
        recommended_books = Book.objects.filter(
            is_approved=True
        ).select_related('submitted_by').prefetch_related('authors').order_by('-id')[:4]
    
    context = {
        'popular_books': popular_books,
        'recommended_books': recommended_books,
        'GENRE_CHOICES': Book.GENRE_CHOICES,
    }
    return render(request, 'home.html', context) 