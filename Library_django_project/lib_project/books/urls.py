from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),  # Общий каталог всех книг
    path('my-library/', views.user_library, name='user_library'),  # Личная библиотека пользователя
    path('book/<int:book_id>/', views.book_detail, name='detail'),
    path('collections/', views.collections_list, name='collections'),
    path('collections/<slug:slug>/', views.collection_detail, name='collection_detail'),
    path('search/', views.search, name='search'),
    path('openlibrary/search/', views.search_openlibrary, name='openlibrary_search'),
    path('openlibrary/add/', views.add_book_from_openlibrary, name='add_from_openlibrary'),
    path('book/add/', views.add_book, name='add_book'),  # Новый URL для ручного добавления книги
]