from django.urls import path
from . import views
from django.http import JsonResponse
from .models import Book

def check_book(request, book_id):
    exists = Book.objects.filter(id=book_id).exists()
    return JsonResponse({'exists': exists, 'book_id': book_id})

app_name = 'books'

urlpatterns = [
    path('check-book/<int:book_id>/', check_book, name='check_book'),  # Временный URL для проверки
    path('catalog/', views.catalog, name='catalog'),  # Общий каталог всех книг
    path('my-library/', views.user_library, name='user_library'),  # Личная библиотека пользователя
    path('my-reviews/', views.user_reviews, name='user_reviews'),
    path('my-quotes/', views.user_quotes, name='user_quotes'),
    path('blacklist/', views.user_blacklist, name='user_blacklist'),
    path('book/<int:book_id>/', views.book_detail, name='detail'),
    path('book/<int:book_id>/add-review/', views.add_review, name='add_review'),  # Новый URL для добавления отзыва
    path('collections/', views.collections_list, name='collections_list'),
    path('collections/genre/<str:genre>/', views.collection_detail, {'collection_type': 'genre'}, name='genre_collection_detail'),
    path('collections/<str:collection_type>/', views.collection_detail, name='collection_detail'),
    path('search/', views.search_books, name='search'),
    path('openlibrary/search/', views.search_openlibrary, name='openlibrary_search'),
    path('openlibrary/add/', views.add_book_from_openlibrary, name='add_from_openlibrary'),
    path('book/add/', views.add_book, name='add_book'),  # URL для ручного добавления книги
    path('book/<int:book_id>/add-to-list/<str:list_type>/', views.add_to_list, name='add_to_list'),  # Новый URL
]