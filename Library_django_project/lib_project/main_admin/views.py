from django.shortcuts import render
from books.models import Book
from django.db.models import Count, Avg
from recommendations.utils import get_book_recommendations
from recommendations.models import UserSurveyProfile
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import get_user_model
from django.utils import timezone
from books.models import Review, Author

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
    has_survey = False
    if request.user.is_authenticated:
        # Проверяем, прошел ли пользователь опрос
        try:
            has_survey = UserSurveyProfile.objects.filter(user=request.user).exists()
        except Exception:
            has_survey = False
            
        # Получаем рекомендации на основе опроса пользователя
        recommendations = get_book_recommendations(request.user.id, limit=4)
        if recommendations:
            # Получаем полные объекты книг с авторами и отправителем
            recommended_books = Book.objects.filter(
                id__in=[book['id'] for book in recommendations]
            ).select_related('submitted_by').prefetch_related('authors')
    
    context = {
        'popular_books': popular_books,
        'recommended_books': recommended_books,
        'GENRE_CHOICES': Book.GENRE_CHOICES,
        'has_survey': has_survey,
    }
    return render(request, 'home.html', context)

@user_passes_test(lambda u: u.is_staff)
def site_statistics(request):
    """Страница со статистикой сайта для администраторов"""
    User = get_user_model()
    today = timezone.now().date()
    
    # Статистика по книгам
    book_stats = {
        'total': Book.objects.count(),
        'approved': Book.objects.filter(is_approved=True).count(),  # Одобренные книги
        'waiting': Book.objects.filter(is_approved=False).count(),  # Книги на рассмотрении
    }
    
    # Статистика по пользователям
    user_stats = {
        'total': User.objects.count(),
        'active': User.objects.filter(is_active=True).count(),
        'staff': User.objects.filter(is_staff=True).count(),
    }
    
    # Статистика по отзывам
    review_stats = {
        'total': Review.objects.count(),
        'today': Review.objects.filter(created_at__date=today).count(),
        'avg_rating': Review.objects.aggregate(avg=Avg('rating'))['avg'] or 0,
    }
    
    # Статистика по авторам
    author_stats = {
        'total': Author.objects.count(),
        'with_books': Author.objects.annotate(book_count=Count('books')).filter(book_count__gt=0).count(),
    }
    
    context = {
        'book_stats': book_stats,
        'user_stats': user_stats,
        'review_stats': review_stats,
        'author_stats': author_stats,
    }
    
    return render(request, 'admin/site_statistics.html', context) 