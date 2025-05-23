from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Count, Avg, Q
from django.contrib import messages
from .models import Book, Author, Review, UserBookRelation, Quote
from .forms import OpenLibrarySearchForm
import requests
from datetime import datetime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.files.temp import NamedTemporaryFile
from django.core.files import File

def home(request):
    """Главная страница"""
    popular_books = Book.objects.filter(
        is_approved=True
    ).select_related('submitted_by').prefetch_related('authors').order_by('-id')[:4]
    
    context = {
        'popular_books': popular_books,
        'GENRE_CHOICES': Book.GENRE_CHOICES,
    }
    return render(request, 'books/home.html', context)

def catalog(request):
    """Общий каталог всех книг библиотеки"""
    genre = request.GET.get('genre')
    ordering = request.GET.get('ordering', 'title')
    page_number = request.GET.get('page', 1)

    books = Book.objects.filter(
        is_approved=True
    ).select_related('submitted_by').prefetch_related('authors')

    if genre:
        books = books.filter(genre=genre)

    # Расширенная сортировка
    if ordering == 'title':
        books = books.order_by('title')
    elif ordering == '-published_date':
        books = books.order_by('-published_date')
    elif ordering == 'published_date':
        books = books.order_by('published_date')
    elif ordering == 'rating':
        books = books.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
    elif ordering == 'popularity':
        books = books.annotate(num_added=Count('user_relations')).order_by('-num_added')
    else:
        books = books.order_by('title')

    # Пагинация
    paginator = Paginator(books, 12)  # 12 книг на странице
    page_obj = paginator.get_page(page_number)

    context = {
        'books': page_obj,
        'GENRE_CHOICES': Book.GENRE_CHOICES,
        'selected_genre': genre,
        'selected_ordering': ordering,
    }
    return render(request, 'books/catalog.html', context)

@login_required
def user_library(request):
    """Личная библиотека пользователя"""
    user_books = UserBookRelation.objects.filter(
        user=request.user
    ).select_related(
        'book', 
        'book__submitted_by'
    ).prefetch_related(
        'book__authors'
    ).order_by('book__title')

    # Группируем книги по спискам для оптимизации шаблона
    reading_now = [rel for rel in user_books if rel.list_type == 'reading']
    want_to_read = [rel for rel in user_books if rel.list_type == 'want_to_read']
    finished = [rel for rel in user_books if rel.list_type == 'finished']
    favorites = [rel for rel in user_books if rel.list_type == 'favorite']

    context = {
        'user_books': user_books,
        'reading_now': reading_now,
        'want_to_read': want_to_read,
        'finished': finished,
        'favorites': favorites,
    }
    return render(request, 'books/user_library.html', context)

def search(request):
    """Поиск книг по названию, автору или жанру"""
    query = request.GET.get('q', '')
    
    if query:
        # Поиск по названию, автору и жанру (регистронезависимый)
        books = Book.objects.filter(
            Q(title__icontains=query) | 
            Q(authors__name__icontains=query) |
            Q(genre__icontains=query),
            is_approved=True
        ).distinct().select_related('submitted_by').prefetch_related('authors')
    else:
        # Если нет запроса, показываем последние добавленные книги
        books = Book.objects.filter(
            is_approved=True
        ).order_by('-created_at')[:10]

    context = {
        'books': books,
        'query': query,
        'no_results': bool(query and not books.exists()),  # Флаг для отображения кнопки поиска в OpenLibrary
    }
    return render(request, 'books/search.html', context)

def book_detail(request, book_id):
    """Детальная страница книги"""
    book = get_object_or_404(Book, id=book_id)
    return render(request, 'books/detail.html', {'book': book})

def collections_list(request):
    """Список всех коллекций книг"""
    collections = UserBookRelation.objects.values('list_type').annotate(
        book_count=Count('id')
    ).order_by('list_type')
    return render(request, 'books/collections/list.html', {'collections': collections})

def collection_detail(request, slug):
    """Детальная страница коллекции"""
    books = UserBookRelation.objects.filter(list_type=slug).select_related('book')
    return render(request, 'books/collections/detail.html', {
        'books': books,
        'collection_name': slug.replace('-', ' ').title()
    })

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

def book_list_view(request):
    genre = request.GET.get('genre')
    ordering = request.GET.get('ordering')  # 'rating' | 'popularity' | 'published'

    books = Book.objects.all()

    if genre:
        books = books.filter(genre=genre)

    if ordering == 'rating':
        books = books.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
    elif ordering == 'popularity':
        books = books.annotate(num_added=Count('user_relations')).order_by('-num_added')
    elif ordering == 'published':
        books = books.order_by('-published_date')

    context = {
        'books': books,
        'selected_genre': genre,
        'selected_ordering': ordering,
        'GENRE_CHOICES': Book.GENRE_CHOICES,
    }
    return render(request, 'books/book_list.html', context)

def external_book_search(title):
    """Поиск книги в Open Library API"""
    url = f"https://openlibrary.org/search.json?q={title}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data from Open Library: {e}")
        return None

def get_book_details(olid):
    """Получение детальной информации о книге по её Open Library ID"""
    url = f"https://openlibrary.org/books/{olid}.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching book details: {e}")
        return None

@login_required
def search_openlibrary(request):
    """Поиск книг в Open Library"""
    form = OpenLibrarySearchForm(request.GET or None)
    results = []
    page_obj = None
    query = request.GET.get('q', '')  # Добавляем сохранение поискового запроса
    
    if form.is_valid():
        title = form.cleaned_data['title']
        search_results = external_book_search(title)
        
        if search_results and 'docs' in search_results:
            results = search_results['docs']
    
    # пагинация
    if results:
        paginator = Paginator(results, 16)  # 16 книг на страницу
        page_number = request.GET.get("page", 1)
        try:
            page_obj = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            page_obj = paginator.get_page(1)

    return render(request, 'books/openlibrary_search.html', {
        'form': form,
        'results': page_obj,
        'query': query,  # Передаем запрос в шаблон для пагинации
    })

def download_cover_from_openlibrary(cover_id):
    """Загрузка обложки книги из OpenLibrary"""
    if not cover_id:
        return None
        
    url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            # Проверяем, что это действительно изображение
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image'):
                return None
                
            # Создаем временный файл
            img_temp = NamedTemporaryFile(delete=True)
            img_temp.write(response.content)
            img_temp.flush()
            
            return img_temp
    except requests.RequestException:
        return None
    return None

@login_required
def add_book_from_openlibrary(request):
    """Добавление книги из Open Library"""
    if request.method == 'POST':
        try:
            book_data = request.POST
            
            # Безопасное получение года публикации
            try:
                first_publish_year = int(book_data.get('first_publish_year', 0))
                century = (first_publish_year // 100) + 1 if first_publish_year > 0 else 20
                published_date = datetime(first_publish_year, 1, 1).date() if first_publish_year else None
            except (ValueError, TypeError):
                first_publish_year = None
                century = 20
                published_date = None
            
            # Создаем или получаем автора
            author_name = book_data.get('author', 'Unknown Author')
            author, _ = Author.objects.get_or_create(
                name=author_name,
                defaults={
                    'century': century,
                    'country': 'Неизвестно'
                }
            )
            
            # Создаем книгу
            book = Book.objects.create(
                title=book_data.get('title', 'Без названия'),
                description=book_data.get('description', ''),
                published_date=published_date,
                world_rating=None,
                is_approved=False,  # Новая книга по умолчанию не одобрена
                submitted_by=request.user,
                genre='other'  # Значение по умолчанию
            )
            
            # Добавляем автора к книге
            book.authors.add(author)
            
            # Загружаем обложку из OpenLibrary
            cover_id = book_data.get('cover_i')
            if cover_id:
                img_temp = download_cover_from_openlibrary(cover_id)
                if img_temp:
                    book.cover.save(
                        f"{book.id}_cover.jpg",
                        File(img_temp),
                        save=True
                    )
            
            messages.success(
                request, 
                f'Книга "{book.title}" успешно добавлена и ожидает одобрения модератора.'
            )
            return redirect('books:detail', book_id=book.id)
            
        except Exception as e:
            messages.error(
                request, 
                f'Произошла ошибка при добавлении книги: {str(e)}'
            )
            return redirect('books:openlibrary_search')
    
    return redirect('books:openlibrary_search')

@login_required
def add_book(request):
    """Добавление книги вручную"""
    if request.method == 'POST':
        try:
            # Создаем или получаем автора
            author_name = request.POST.get('author')
            author, _ = Author.objects.get_or_create(
                name=author_name,
                defaults={
                    'century': 20,  # Значение по умолчанию
                    'country': 'Неизвестно'
                }
            )
            
            # Создаем книгу
            book = Book.objects.create(
                title=request.POST.get('title'),
                description=request.POST.get('description', ''),
                published_date=request.POST.get('published_date'),
                genre=request.POST.get('genre'),
                is_approved=False,  # Новая книга по умолчанию не одобрена
                submitted_by=request.user
            )
            
            # Добавляем автора к книге
            book.authors.add(author)
            
            # Обрабатываем загруженную обложку
            if request.FILES.get('cover'):
                book.cover = request.FILES['cover']
                book.save()
            
            messages.success(
                request, 
                f'Книга "{book.title}" успешно добавлена и ожидает одобрения модератора.'
            )
            return redirect('books:detail', book_id=book.id)
            
        except Exception as e:
            messages.error(
                request, 
                f'Произошла ошибка при добавлении книги: {str(e)}'
            )
            return redirect('books:add_book')
    
    context = {
        'GENRE_CHOICES': Book.GENRE_CHOICES,
    }
    return render(request, 'books/add_book.html', context)