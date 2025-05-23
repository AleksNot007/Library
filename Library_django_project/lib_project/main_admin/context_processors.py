from django.contrib.auth import get_user_model
from books.models import Book, Author, Review
from datetime import date

def admin_stats(request):
    if not request.path.startswith('/admin/'):
        return {}
        
    User = get_user_model()
    return {
        'book_count': Book.objects.count(),
        'user_count': User.objects.count(),
        'author_count': Author.objects.count(),
        'review_count': Review.objects.count(),
        'today': date.today().isoformat(),
    } 