from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Count, Avg, Q, Case, When, IntegerField, Value
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from .models import Book, Author, Review, UserBookRelation, Quote, Collection
from .forms import OpenLibrarySearchForm, BookForm, ReviewForm, QuoteForm
import requests
from datetime import datetime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.files.temp import NamedTemporaryFile
from django.core.files import File
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from urllib.parse import quote
import re
from django.utils.text import slugify
from django.http import Http404
from django.utils.safestring import mark_safe
from django.urls import reverse
from users.models import ModeratorMessage  # Обновляем импорт ModeratorMessage из приложения users

def home(request):
    """Главная страница"""
    # Получаем популярные книги
    popular_books = Book.objects.filter(
        is_approved=True
    ).annotate(
        readers_count=Count('user_relations', distinct=True)
    ).select_related('submitted_by').prefetch_related('authors').order_by('-readers_count')[:8]
    
    # Получаем лучшие книги по жанрам с улучшенной фильтрацией
    best_books_by_genre = {}
    for genre_code, genre_name in Book.GENRE_CHOICES:
        # Получаем книги с высоким рейтингом и достаточным количеством отзывов
        best_books = Book.objects.filter(
            is_approved=True,
            genre=genre_code,
            world_rating__gte=4.5  # Снижаем порог рейтинга для большего охвата
        ).annotate(
            reviews_count=Count('reviews'),
            readers_count=Count('user_relations', distinct=True)
        ).filter(
            reviews_count__gte=3  # Минимум 3 отзыва для объективности
        ).select_related('submitted_by').prefetch_related('authors').order_by('-world_rating', '-readers_count')[:12]
        
        if best_books.exists():
            # Добавляем дополнительную информацию о жанре
            total_books = Book.objects.filter(genre=genre_code, is_approved=True).count()
            avg_rating = best_books.aggregate(Avg('world_rating'))['world_rating__avg']
            
            best_books_by_genre[genre_code] = {
                'name': genre_name,
                'books': best_books,
                'total_books': total_books,
                'avg_rating': round(avg_rating, 1) if avg_rating else None
            }
    
    # Сортируем жанры по количеству книг
    best_books_by_genre = dict(sorted(
        best_books_by_genre.items(),
        key=lambda x: x[1]['total_books'],
        reverse=True
    ))
    
    # Получаем рекомендации для авторизованного пользователя
    recommended_books = None
    if request.user.is_authenticated:
        # Сначала пробуем получить рекомендации из системы рекомендаций
        if hasattr(request.user, 'test_recommendations'):
            recommended_books = request.user.test_recommendations.all()[:8]
        
        # Если нет рекомендаций из системы, используем базовые рекомендации
        if not recommended_books:
            # Получаем жанры из прочитанных книг
            user_genres = Book.objects.filter(
                user_relations__user=request.user
            ).values_list('genre', flat=True).distinct()
            
            # Если есть жанры, рекомендуем книги из этих жанров
            if user_genres:
                recommended_books = Book.objects.filter(
                    genre__in=user_genres,
                    is_approved=True
                ).exclude(
                    user_relations__user=request.user
                ).select_related('submitted_by').prefetch_related('authors').order_by('?')[:8]
            # Если нет жанров, рекомендуем популярные книги
            else:
                recommended_books = popular_books
    
    context = {
        'popular_books': popular_books,
        'recommended_books': recommended_books,
        'GENRE_CHOICES': Book.GENRE_CHOICES,
        'best_books_by_genre': best_books_by_genre,
    }
    return render(request, 'books/home.html', context)

def catalog(request):
    """Каталог книг с фильтрацией и сортировкой"""
    books = Book.objects.filter(
        is_approved=True
    ).select_related('submitted_by').prefetch_related('authors', 'reviews')
    
    # Фильтрация по жанру
    genre = request.GET.get('genre')
    if genre:
        books = books.filter(genre=genre)
    
    # Сортировка
    ordering = request.GET.get('ordering', '-created_at')
    if ordering == 'rating':
        books = books.order_by('-site_rating')
    elif ordering == 'popularity':
        books = books.annotate(relations_count=Count('user_relations')).order_by('-relations_count')
    else:
        books = books.order_by(ordering)
    
    # Поиск
    query = request.GET.get('q')
    if query:
        books = books.filter(title__icontains=query)
    
    # Пагинация
    paginator = Paginator(books, 12)
    page = request.GET.get('page')
    books = paginator.get_page(page)
    
    context = {
        'books': books,
        'query': query,
        'selected_genre': genre,
        'selected_ordering': ordering,
        'GENRE_CHOICES': Book.GENRE_CHOICES
    }
    
    return render(request, 'books/catalog.html', context)

@login_required
def user_library(request):
    """Личная библиотека пользователя"""
    # Получаем книги пользователя
    user_books = UserBookRelation.objects.filter(
        user=request.user
    ).select_related(
        'book', 
        'book__submitted_by'
    ).prefetch_related(
        'book__authors'
    )

    # Группируем книги по спискам
    reading_now = [rel for rel in user_books if rel.list_type == 'in_progress']
    want_to_read = [rel for rel in user_books if rel.list_type == 'want']
    finished = [rel for rel in user_books if rel.list_type == 'read']
    favorites = [rel for rel in user_books if rel.list_type == 'favorite']
    stopped = [rel for rel in user_books if rel.list_type == 'stop']  # Добавляем стоп-лист

    context = {
        'reading_now': reading_now,
        'want_to_read': want_to_read,
        'finished': finished,
        'favorites': favorites,
        'stopped': stopped,  # Добавляем в контекст
    }

    return render(request, 'lib/my_library.html', context)

@login_required
def user_reviews(request):
    """Страница отзывов пользователя"""
    user_reviews = Review.objects.filter(
        user=request.user
    ).select_related(
        'book'
    ).prefetch_related(
        'book__authors'
    ).order_by('-created_at')

    return render(request, 'lib/user_reviews.html', {'user_reviews': user_reviews})

@login_required
def user_quotes(request):
    """Страница цитат пользователя"""
    user_quotes = Quote.objects.filter(
        user=request.user
    ).select_related(
        'book'
    ).prefetch_related(
        'book__authors'
    ).order_by('-created_at')

    return render(request, 'lib/user_quotes.html', {'user_quotes': user_quotes})

@login_required
def user_blacklist(request):
    """Страница черного списка пользователя"""
    blacklisted_books = UserBookRelation.objects.filter(
        user=request.user,
        list_type='blacklist'
    ).select_related(
        'book'
    ).prefetch_related(
        'book__authors'
    ).order_by('book__title')

    return render(request, 'lib/user_blacklist.html', {
        'blacklisted_books': [rel.book for rel in blacklisted_books]
    })

def search(request):
    """Поиск книг по названию, автору или жанру"""
    query = request.GET.get('q', '').strip()
    format = request.GET.get('format', 'html')  # Добавляем параметр для возврата JSON при AJAX-запросах
    
    if query:
        # Разбиваем поисковый запрос на слова
        search_words = query.split()
        
        # Создаем Q-объекты для поиска по названию и автору
        title_query = Q()
        author_query = Q()
        
        for word in search_words:
            title_query |= Q(title__icontains=word)
            author_query |= Q(authors__name__icontains=word)
        
        # Объединяем условия поиска
        books = Book.objects.filter(
            (title_query | author_query) & Q(is_approved=True)
        ).distinct().select_related('submitted_by').prefetch_related('authors')
        
        # Сортируем результаты по релевантности
        books = books.annotate(
            relevance=Count('id')  # Базовая релевантность
        ).order_by('-relevance', 'title')
        
        if format == 'json':
            # Для AJAX-запросов возвращаем JSON
            books_data = [{
                'id': book.id,
                'title': book.title,
                'authors': [author.name for author in book.authors.all()],
                'cover_url': book.cover.url if book.cover else None,
            } for book in books[:20]]  # Ограничиваем результаты
            return JsonResponse({'books': books_data})
    else:
        books = Book.objects.filter(is_approved=True).order_by('-created_at')[:10]
    
    # Для обычных запросов возвращаем HTML
    context = {
        'books': books,
        'query': query,
    }
    return render(request, 'books/search.html', context)

def detail(request, book_id):
    """Детальная страница книги"""
    book = get_object_or_404(Book, id=book_id)
    
    # Получаем текущий список книги для пользователя
    current_list_type = None
    if request.user.is_authenticated:
        user_relation = UserBookRelation.objects.filter(
            user=request.user,
            book=book
        ).first()
        if user_relation:
            current_list_type = user_relation.list_type
    
    context = {
        'book': book,
        'current_list_type': current_list_type
    }
    return render(request, 'books/detail.html', context)

@login_required
def collections_list(request):
    """Список глобальных подборок книг"""
    # Создаем словарь с названиями жанров
    genre_names = dict(Book.GENRE_CHOICES)
    
    # Получаем топ-100 книг по рейтингу для каждого жанра
    genre_top_books = {}
    for genre_code, genre_name in Book.GENRE_CHOICES:
        # Получаем книги для жанра
        top_books = Book.objects.filter(
            genre=genre_code,
            is_approved=True
        ).annotate(
            avg_rating=Avg('reviews__rating'),
            readers_count=Count('user_relations', distinct=True)
        ).filter(
            avg_rating__gte=4.5
        ).order_by('-avg_rating', '-readers_count')[:100]
        
        # Добавляем жанр в словарь независимо от наличия книг
        genre_top_books[genre_code] = top_books

    # Получаем популярные книги (добавленные большинством пользователей)
    total_users = get_user_model().objects.count()
    popular_books = Book.objects.filter(
        is_approved=True
    ).annotate(
        readers_count=Count('user_relations', distinct=True)
    ).filter(
        readers_count__gte=total_users * 0.3  # Книги, которые есть у 30% пользователей
    ).order_by('-readers_count')[:100]

    # Получаем книги, которые пользователи чаще всего добавляют в библиотеку
    most_added_books = Book.objects.filter(
        is_approved=True
    ).annotate(
        total_adds=Count('user_relations')
    ).order_by('-total_adds')[:100]

    # Топ-100 по рейтингу среди всех книг
    top_rated_books = Book.objects.filter(
        is_approved=True
    ).annotate(
        avg_rating=Avg('reviews__rating'),
        reviews_count=Count('reviews')
    ).filter(
        avg_rating__gte=4.5,
        reviews_count__gte=5  # Минимум 5 отзывов для объективности
    ).order_by('-avg_rating', '-reviews_count')[:100]

    context = {
        'genre_top_books': genre_top_books,
        'popular_books': popular_books,
        'most_added_books': most_added_books,
        'top_rated_books': top_rated_books,
        'dict': genre_names,  # Добавляем словарь с названиями жанров
    }
    return render(request, 'books/collections/list.html', context)

def genre_collection_detail(request, genre):
    """Детальная страница подборки книг определенного жанра"""
    # Создаем словарь для преобразования русских названий в коды
    genre_name_to_code = {name: code for code, name in Book.GENRE_CHOICES}
    
    # Если передано русское название жанра, получаем его код
    genre_code = genre_name_to_code.get(genre, genre)
    
    # Получаем топ книг конкретного жанра
    books = Book.objects.filter(
        genre=genre_code,
        is_approved=True,
        world_rating__gte=4.5,  # Рейтинг >= 4.5
        world_rating__lte=5.0   # Рейтинг <= 5.0
    ).order_by('-world_rating', '-created_at')[:100]
    
    # Получаем русское название жанра из кода
    genre_display_name = dict(Book.GENRE_CHOICES).get(genre_code, genre_code)
    title = f"Топ-100 книг жанра {genre_display_name}"
    
    # Пагинация
    paginator = Paginator(books, 12)  # 12 книг на странице
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': title,
        'books': page_obj,
        'genre': genre,
        'genre_display_name': genre_display_name,
    }
    return render(request, 'books/collections/genre_detail.html', context)

@login_required
def collection_detail(request, slug):
    """Детальная страница подборки"""
    collection = get_object_or_404(Collection, slug=slug)
    
    # Проверяем права доступа
    if not collection.is_public and collection.created_by != request.user and not request.user.is_staff:
        messages.error(request, 'У вас нет доступа к этой подборке')
        return redirect('books:user_collections')
    
    # Получаем книги подборки с авторами
    books = collection.books.select_related('submitted_by').prefetch_related('authors').all()
    
    context = {
        'collection': collection,
        'books': books,
    }
    return render(request, 'books/collections/collection_detail.html', context)

@login_required
def create_collection(request):
    """Создание новой подборки"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        type = request.POST.get('type', 'custom')
        is_public = request.POST.get('is_public', 'true') == 'true'
        
        if not title:
            messages.error(request, 'Название подборки обязательно')
            return redirect('books:create_collection')
        
        # Создаем slug из названия
        slug = slugify(title)
        base_slug = slug
        counter = 1
        
        # Проверяем уникальность slug
        while Collection.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Создаем подборку
        collection = Collection.objects.create(
            title=title,
            description=description,
            type=type,
            slug=slug,
            is_public=is_public,
            created_by=request.user
        )
        
        # Обрабатываем загруженную обложку
        if request.FILES.get('cover'):
            collection.cover = request.FILES['cover']
            collection.save()
        
        messages.success(request, f'Подборка "{title}" успешно создана')
        return redirect('books:collection_detail', slug=collection.slug)
    
    context = {
        'collection_types': Collection.COLLECTION_TYPES,
    }
    return render(request, 'books/collections/create.html', context)

@login_required
def edit_collection(request, slug):
    """Редактирование подборки"""
    collection = get_object_or_404(Collection, slug=slug)
    
    # Проверяем права на редактирование
    if collection.created_by != request.user and not request.user.is_staff:
        messages.error(request, 'У вас нет прав на редактирование этой подборки')
        return redirect('books:collection_detail', slug=slug)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        type = request.POST.get('type', 'custom')
        is_public = request.POST.get('is_public', 'true') == 'true'
        
        if not title:
            messages.error(request, 'Название подборки обязательно')
            return redirect('books:edit_collection', slug=slug)
        
        # Обновляем данные подборки
        collection.title = title
        collection.description = description
        collection.type = type
        collection.is_public = is_public
        
        # Обрабатываем загруженную обложку
        if request.FILES.get('cover'):
            collection.cover = request.FILES['cover']
        
        collection.save()
        messages.success(request, f'Подборка "{title}" успешно обновлена')
        return redirect('books:collection_detail', slug=collection.slug)
    
    context = {
        'collection': collection,
        'collection_types': Collection.COLLECTION_TYPES,
    }
    return render(request, 'books/collections/edit.html', context)

@login_required
@require_http_methods(["POST"])
def add_book_to_collection(request, slug, book_id):
    """Добавление книги в подборку"""
    collection = get_object_or_404(Collection, slug=slug)
    book = get_object_or_404(Book, id=book_id)
    
    # Проверяем права на редактирование
    if collection.created_by != request.user and not request.user.is_staff:
        return JsonResponse({
            'status': 'error',
            'message': 'У вас нет прав на редактирование этой подборки'
        }, status=403)
    
    # Проверяем, не добавлена ли уже книга
    if book in collection.books.all():
        return JsonResponse({
            'status': 'info',
            'message': 'Эта книга уже есть в подборке'
        })
    
    # Добавляем книгу в подборку
    collection.books.add(book)
    
    return JsonResponse({
        'status': 'success',
        'message': f'Книга добавлена в подборку "{collection.title}"'
    })

@login_required
@require_http_methods(["POST"])
def remove_book_from_collection(request, collection_slug, book_id):
    """Удаление книги из подборки"""
    collection = get_object_or_404(Collection, slug=collection_slug)
    book = get_object_or_404(Book, id=book_id)
    
    # Проверяем права на редактирование
    if collection.created_by != request.user and not request.user.is_staff:
        return JsonResponse({
            'status': 'error',
            'message': 'У вас нет прав на редактирование этой подборки'
        }, status=403)
    
    # Удаляем книгу из подборки
    collection.books.remove(book)
    
    return JsonResponse({
        'status': 'success',
        'message': f'Книга удалена из подборки "{collection.title}"'
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

def external_book_search(title, language=None):
    """Поиск книги в Open Library API"""
    if not title:
        return None
        
    # Кодируем запрос для URL
    encoded_title = quote(title)
    
    # Формируем базовый URL
    base_url = "https://openlibrary.org/search.json"
    
    try:
        # Если указан конкретный язык, ищем только по нему
        if language:
            url = f"{base_url}?q={encoded_title}&language={language}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        
        # Иначе делаем общий поиск без фильтра по языку
        url = f"{base_url}?q={encoded_title}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
        
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching data from Open Library: {e}")
        return None

@login_required
def openlibrary_search(request):
    """Поиск книг в OpenLibrary API"""
    query = request.GET.get('q', '')
    language = request.GET.get('language', '')
    results = []
    page_obj = None
    available_languages = set()
    
    if query:
        search_results = external_book_search(query, language if language else None)
        
        if search_results and 'docs' in search_results:
            # Собираем все доступные языки из результатов
            for doc in search_results['docs']:
                if 'language' in doc:
                    available_languages.update(doc.get('language', []))
            
            # Группируем результаты по названию книги для объединения разных изданий
            books_by_title = {}
            for doc in search_results['docs']:
                title = doc.get('title', '').strip()
                if not title:
                    continue
                
                if title not in books_by_title:
                    books_by_title[title] = {
                        'title': title,
                        'author_name': doc.get('author_name', []),
                        'first_publish_year': doc.get('first_publish_year'),
                        'language': doc.get('language', []),
                        'covers': [],
                        'is_russian': 'language' in doc and 'rus' in doc.get('language', []),
                        'has_russian_title': bool(is_russian_text(title)),
                        'editions': []
                    }
                
                # Добавляем информацию об издании
                edition_info = {
                    'cover_i': doc.get('cover_i'),
                    'language': doc.get('language', []),
                    'publish_year': doc.get('publish_year', []),
                }
                books_by_title[title]['editions'].append(edition_info)
                
                # Добавляем обложку, если она есть
                if doc.get('cover_i'):
                    books_by_title[title]['covers'].append({
                        'id': doc['cover_i'],
                        'is_russian': 'language' in doc and 'rus' in doc.get('language', [])
                    })
            
            # Преобразуем словарь в список и выбираем лучшие обложки
            results = []
            for book_info in books_by_title.values():
                # Сортируем обложки: русские впереди
                book_info['covers'].sort(key=lambda x: (not x['is_russian']))
                # Выбираем лучшую обложку
                if book_info['covers']:
                    book_info['cover_i'] = book_info['covers'][0]['id']
                
                results.append(book_info)
            
            # Сортируем результаты
            if not language:
                results.sort(key=lambda x: (
                    not x['is_russian'],  # Сначала русские издания
                    not x['has_russian_title'],  # Затем книги с русскими названиями
                    x['title'].lower()  # Потом по алфавиту
                ))
            else:
                # Если выбран конкретный язык, фильтруем по нему
                results = [
                    book for book in results
                    if any(language in edition.get('language', []) for edition in book['editions'])
                ]

    # Пагинация
    if results:
        paginator = Paginator(results, 16)  # 16 книг на страницу
        page_number = request.GET.get("page", 1)
        try:
            page_obj = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            page_obj = paginator.get_page(1)

    # Готовим список языков для фильтра
    language_choices = sorted([
        (code, get_language_name(code))
        for code in available_languages
        if get_language_name(code)  # Только языки, для которых есть названия
    ], key=lambda x: x[1])

    # Получаем список жанров из модели Book
    genre_choices = Book.GENRE_CHOICES

    context = {
        'form': OpenLibrarySearchForm(initial={'q': query, 'language': language}),
        'results': page_obj,
        'query': query,
        'selected_language': language,
        'language_choices': language_choices,
        'GENRE_CHOICES': genre_choices,
    }

    return render(request, 'books/openlibrary_search.html', context)

def is_russian_text(text):
    """Проверяет, содержит ли текст русские буквы"""
    if not text:
        return False
    return bool(re.search('[а-яА-Я]', text))

def get_language_name(code):
    """Возвращает название языка по его коду"""
    languages = {
        'rus': 'Русский',
        'eng': 'Английский',
        'fre': 'Французский',
        'ger': 'Немецкий',
        'spa': 'Испанский',
        'ita': 'Итальянский',
        'chi': 'Китайский',
        'jpn': 'Японский',
        'kor': 'Корейский',
        'ara': 'Арабский',
        'por': 'Португальский',
        'hin': 'Хинди',
        'ben': 'Бенгальский',
        'pol': 'Польский',
        'ukr': 'Украинский',
        'vie': 'Вьетнамский',
        'tur': 'Турецкий',
        'per': 'Персидский',
        'heb': 'Иврит',
        'tha': 'Тайский',
    }
    return languages.get(code)

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

def check_book(request, book_id):
    """Проверяет существование книги по ID"""
    exists = Book.objects.filter(id=book_id).exists()
    return JsonResponse({'exists': exists, 'book_id': book_id})

def remove_duplicate_books():
    """Удаление дубликатов книг с одинаковым названием и автором"""
    # Получаем все книги
    books = Book.objects.all().prefetch_related('authors')
    
    # Словарь для хранения уникальных книг
    unique_books = {}
    duplicates = []
    
    for book in books:
        # Получаем авторов книги, сортируем их имена для консистентного сравнения
        authors = sorted([author.name.lower().strip() for author in book.authors.all()])
        # Создаем ключ из названия книги и авторов
        key = (book.title.lower().strip(), tuple(authors))
        
        if key in unique_books:
            # Если книга уже существует, проверяем, какую оставить
            existing_book = unique_books[key]
            
            # Оставляем книгу с обложкой или более старую
            if (not existing_book.cover and book.cover) or \
               (existing_book.created_at > book.created_at):
                duplicates.append(existing_book)
                unique_books[key] = book
            else:
                duplicates.append(book)
        else:
            # Если это первая книга с таким названием и авторами
            unique_books[key] = book
    
    # Удаляем дубликаты
    for duplicate in duplicates:
        duplicate.delete()

    return len(duplicates)

def check_book_exists(title, author_name):
    """Проверяет существование книги по названию и автору"""
    title = title.lower().strip()
    author_name = author_name.lower().strip()
    
    # Ищем книги с похожим названием
    similar_books = Book.objects.filter(
        title__iexact=title
    ).prefetch_related('authors')
    
    # Проверяем авторов
    for book in similar_books:
        book_authors = [author.name.lower().strip() for author in book.authors.all()]
        if author_name in book_authors:
            return True, book
    
    return False, None

@login_required
def add_from_openlibrary(request):
    """Добавление книги из Open Library"""
    if request.method == 'POST':
        try:
            book_data = request.POST
            
            # Проверяем обязательные поля
            required_fields = ['title', 'author']
            missing_fields = [field for field in required_fields if not book_data.get(field)]
            
            if missing_fields:
                messages.error(
                    request, 
                    f'Отсутствуют обязательные поля: {", ".join(missing_fields)}'
                )
                return redirect('books:openlibrary_search')

            title = book_data.get('title', '').strip()
            author_name = book_data.get('author', '').strip()

            # Проверяем существование книги
            exists, existing_book = check_book_exists(title, author_name)
            if exists:
                messages.error(
                    request,
                    f'Книга "{existing_book.title}" уже существует в библиотеке.'
                )
                return redirect('books:detail', book_id=existing_book.id)
            
            # Безопасное получение года публикации
            try:
                first_publish_year = int(book_data.get('first_publish_year', 0))
                century = (first_publish_year // 100) + 1 if first_publish_year > 0 else None
                published_date = datetime(first_publish_year, 1, 1).date() if first_publish_year else None
            except (ValueError, TypeError):
                first_publish_year = None
                century = None
                published_date = None
            
            # Создаем или получаем автора
            author, _ = Author.objects.get_or_create(
                name=author_name,
                defaults={
                    'century': century or 20,
                    'country': book_data.get('author_country', 'Неизвестно')
                }
            )

            # Получаем комментарии пользователя для модератора
            user_comments = book_data.get('user_comments', '').strip()
            
            # Создаем книгу
            book = Book.objects.create(
                title=title,
                description=book_data.get('description', '').strip() or 'Описание отсутствует',
                published_date=published_date,
                world_rating=None,
                is_approved=False,  # Книга всегда требует одобрения модератора
                submitted_by=request.user,
                genre=book_data.get('genre', 'other'),
                moderation_comment=user_comments
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

            # Создаем сообщение для модератора
            ModeratorMessage.objects.create(
                user=request.user,
                book=book,
                message_type='book_submitted',
                message=f'Книга "{book.title}" добавлена из OpenLibrary и ожидает модерации.\n'
                        f'Комментарии пользователя: {user_comments if user_comments else "Нет комментариев"}'
            )
            
            messages.success(
                request, 
                'Книга отправлена на модерацию. После проверки модератором вы сможете добавить её в свои списки.'
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
            # Проверяем обязательные поля
            title = request.POST.get('title', '').strip()
            author_name = request.POST.get('author', '').strip()
            genre = request.POST.get('genre')

            if not all([title, author_name, genre]):
                messages.error(
                    request,
                    'Пожалуйста, заполните все обязательные поля: название, автор и жанр.'
                )
                return redirect('books:add_book')

            # Проверяем существование книги
            exists, existing_book = check_book_exists(title, author_name)
            if exists:
                messages.error(
                    request,
                    f'Книга "{existing_book.title}" уже существует в библиотеке.'
                )
                return redirect('books:detail', book_id=existing_book.id)

            # Создаем или получаем автора
            author, _ = Author.objects.get_or_create(
                name=author_name,
                defaults={
                    'century': 20,  # Значение по умолчанию
                    'country': 'Неизвестно'
                }
            )
            
            # Обработка года публикации
            published_year = request.POST.get('published_date')
            published_date = None
            current_year = datetime.now().year

            if published_year:
                try:
                    year = int(published_year)
                    if year < 1 or year > current_year:
                        messages.warning(
                            request,
                            f'Год публикации должен быть между 1 и {current_year}. Поле будет оставлено пустым.'
                        )
                    else:
                        published_date = datetime(year, 1, 1).date()
                except ValueError:
                    messages.warning(
                        request,
                        'Введите корректный год публикации (например: 1984). Поле будет оставлено пустым.'
                    )

            # Обработка количества страниц
            pages = request.POST.get('pages')
            try:
                pages = int(pages) if pages else None
                if pages is not None and pages < 1:
                    messages.warning(
                        request,
                        'Количество страниц должно быть положительным числом. Поле будет оставлено пустым.'
                    )
                    pages = None
            except ValueError:
                messages.warning(
                    request,
                    'Введите корректное количество страниц. Поле будет оставлено пустым.'
                )
                pages = None
            
            # Создаем книгу
            book = Book.objects.create(
                title=title,
                description=request.POST.get('description', '').strip(),
                published_date=published_date,
                pages=pages,  # Добавляем количество страниц
                genre=genre,
                is_approved=False,  # Книга не одобрена
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
                'Книга отправлена на модерацию. После проверки модератором она появится в каталоге.'
            )
            
            return redirect('books:catalog')
            
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

# Обновляем логику модерации в админке
def approve_book(modeladmin, request, queryset):
    """Одобрение книги модератором"""
    # Сначала удаляем дубликаты
    duplicates_removed = remove_duplicate_books()
    if duplicates_removed > 0:
        messages.info(request, f'Удалено {duplicates_removed} дубликатов книг')
    
    for book in queryset:
        # Проверяем, не одобрена ли уже книга
        if not book.is_approved:
            # Проверяем на дубликаты перед одобрением
            exists, existing_book = check_book_exists(book.title, book.authors.first().name if book.authors.exists() else '')
            if exists and existing_book.id != book.id:
                messages.warning(
                    request,
                    f'Книга "{book.title}" является дубликатом существующей книги "{existing_book.title}" и будет удалена.'
                )
                book.delete()
                continue
            
            book.is_approved = True
            book.needs_moderation = False
            book.save()
            
            # Создаем сообщение для пользователя с ссылкой на книгу
            ModeratorMessage.objects.create(
                user=book.submitted_by,
                book=book,
                message_type='book_approved',
                message=f'Ваша книга "{book.title}" была одобрена и добавлена в каталог. '
                        f'<a href="{reverse("books:detail", args=[book.id])}">Перейти к книге</a>'
            )
            
            messages.success(
                request,
                f'Книга "{book.title}" успешно одобрена и добавлена в каталог.'
            )

def reject_book(request, book_id):
    """Отклонение книги модератором"""
    book = get_object_or_404(Book, id=book_id)
    
    # Отмечаем книгу как отклоненную
    book.is_approved = False
    book.needs_moderation = False
    book.save()
    
    # Создаем сообщение для пользователя без ссылки
    ModeratorMessage.objects.create(
        user=book.submitted_by,
        book=book,
        message_type='book_rejected',
        message=f'Ваша книга "{book.title}" была отклонена модератором.'
    )
    
    # Удаляем книгу
    book.delete()
    
    messages.warning(request, f'Книга "{book.title}" была отклонена и удалена')
    return redirect('books:catalog')

@login_required
@require_POST
def update_progress(request, book_id):
    """Обновление прогресса чтения книги"""
    book = get_object_or_404(Book, id=book_id)
    try:
        progress_pages = int(request.POST.get('progress_pages', 0))
        if progress_pages < 0 or progress_pages > book.pages:
            return JsonResponse({
                'status': 'error',
                'message': 'Некорректное количество страниц'
            }, status=400)

        relation, created = UserBookRelation.objects.get_or_create(
            user=request.user,
            book=book
        )
        relation.progress_pages = progress_pages
        relation.save()  # progress будет автоматически обновлен

        return JsonResponse({
            'status': 'success',
            'message': 'Прогресс обновлен',
            'progress': relation.progress
        })
    except ValueError:
        return JsonResponse({
            'status': 'error',
            'message': 'Некорректные данные'
        }, status=400)

@login_required
@require_POST
def update_notes(request, book_id):
    """Обновление личных заметок к книге"""
    book = get_object_or_404(Book, id=book_id)
    notes = request.POST.get('notes', '').strip()

    relation, created = UserBookRelation.objects.get_or_create(
        user=request.user,
        book=book
    )
    relation.notes = notes
    relation.save()

    return JsonResponse({
        'status': 'success',
        'message': 'Заметки обновлены'
    })

@login_required
@require_POST
def add_to_list(request, book_id, list_type):
    """Добавление книги в различные списки пользователя"""
    try:
        # Проверяем допустимость типа списка
        valid_list_types = ['want', 'reading', 'read', 'stop', 'favorite', 'blacklist', 'in_progress']
        if list_type not in valid_list_types:
            return JsonResponse({
                'status': 'error',
                'message': 'Некорректный тип списка'
            }, status=400)

        book = get_object_or_404(Book, id=book_id)
        
        # Проверяем, одобрена ли книга
        if not book.is_approved:
            return JsonResponse({
                'status': 'error',
                'message': 'Книга ожидает одобрения модератора. Вы сможете добавить её в список после проверки.'
            }, status=403)

        relation, created = UserBookRelation.objects.get_or_create(
            user=request.user,
            book=book,
            defaults={'list_type': list_type}
        )

        if not created:
            # Если отношение уже существует, обновляем тип списка
            relation.list_type = list_type
            # Если книга добавляется в избранное
            if list_type == 'favorite':
                relation.is_favourite = True
            elif list_type != 'favorite' and relation.is_favourite:
                relation.is_favourite = False
            relation.save()

        # Получаем читаемое название списка
        list_names = {
            'want': 'Хочу прочитать',
            'reading': 'Читаю',
            'read': 'Прочитано',
            'stop': 'Отложено',
            'favorite': 'Избранное',
            'blacklist': 'Черный список',
            'in_progress': 'Читаю сейчас'
        }
        list_name = list_names.get(list_type, list_type)

        return JsonResponse({
            'status': 'success',
            'message': f'Книга "{book.title}" добавлена в список "{list_name}"'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Произошла ошибка при добавлении книги в список: {str(e)}'
        }, status=500)

@login_required
@require_POST
def add_quote(request, book_id):
    """Добавление цитаты из книги"""
    book = get_object_or_404(Book, id=book_id)
    form = QuoteForm(request.POST)
    
    if form.is_valid():
        quote = form.save(commit=False)
        quote.book = book
        quote.user = request.user
        quote.save()
        
        messages.success(request, 'Цитата успешно добавлена')
        return redirect('books:detail', book_id=book.id)
    
    messages.error(request, 'Ошибка при добавлении цитаты')
    return redirect('books:detail', book_id=book.id)

@login_required
@require_POST
def add_review(request, book_id):
    """Добавление отзыва на книгу"""
    book = get_object_or_404(Book, id=book_id)
    form = ReviewForm(request.POST)
    
    if form.is_valid():
        review = form.save(commit=False)
        review.book = book
        review.user = request.user
        review.save()
        
        # Обновляем рейтинг книги
        book.site_rating = book.reviews.aggregate(Avg('rating'))['rating__avg']
        book.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Отзыв добавлен'
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Некорректные данные'
    }, status=400)

def book_detail(request, book_id):
    """Детальная информация о книге"""
    book = get_object_or_404(Book, id=book_id)
    user_relation = None
    
    if request.user.is_authenticated:
        user_relation = UserBookRelation.objects.filter(
            user=request.user,
            book=book
        ).first()
    
    context = {
        'book': book,
        'user_book_relation': user_relation,
        'reviews': book.reviews.select_related('user').order_by('-created_at'),
        'quotes': book.quotes.select_related('user').order_by('-created_at')
    }
    
    return render(request, 'books/detail.html', context)

@login_required
def moderator_messages(request):
    """Страница сообщений от модератора"""
    # Получаем все сообщения пользователя
    messages = ModeratorMessage.objects.filter(user=request.user)
    
    # Помечаем все непрочитанные сообщения как прочитанные
    unread_messages = messages.filter(is_read=False)
    if unread_messages.exists():
        unread_messages.update(is_read=True)
    
    # Группируем сообщения по типам
    context = {
        'approved_books': messages.filter(message_type='book_approved'),
        'rejected_books': messages.filter(message_type='book_rejected'),
        'general_messages': messages.filter(message_type='general'),
    }
    
    return render(request, 'books/moderator_messages.html', context)

@login_required
def edit_book(request, book_id):
    """Редактирование книги"""
    book = get_object_or_404(Book, id=book_id)
    
    # Проверяем права на редактирование
    if book.submitted_by != request.user and not request.user.is_staff:
        messages.error(request, 'У вас нет прав на редактирование этой книги')
        return redirect('books:detail', book_id=book.id)
    
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            book = form.save(commit=False)
            book.needs_moderation = True  # Отправляем на повторную модерацию
            book.save()
            form.save_m2m()  # Сохраняем связи many-to-many
            
            messages.success(request, 'Книга успешно обновлена и отправлена на модерацию')
            return redirect('books:detail', book_id=book.id)
    else:
        form = BookForm(instance=book)
    
    return render(request, 'books/edit_book.html', {
        'form': form,
        'book': book
    })

@login_required
def delete_book(request, book_id):
    """Удаление книги"""
    book = get_object_or_404(Book, id=book_id)
    
    # Проверяем права на удаление
    if book.submitted_by != request.user and not request.user.is_staff:
        messages.error(request, 'У вас нет прав на удаление этой книги')
        return redirect('books:detail', book_id=book.id)
    
    if request.method == 'POST':
        book.delete()
        messages.success(request, 'Книга успешно удалена')
        return redirect('books:catalog')
    
    return render(request, 'books/delete_book.html', {'book': book})

@login_required
def edit_quote(request, quote_id):
    """Редактирование цитаты"""
    quote = get_object_or_404(Quote, id=quote_id)
    
    # Проверяем права на редактирование
    if quote.user != request.user:
        messages.error(request, 'У вас нет прав на редактирование этой цитаты')
        return redirect('books:detail', book_id=quote.book.id)
    
    if request.method == 'POST':
        form = QuoteForm(request.POST, instance=quote)
        if form.is_valid():
            form.save()
            messages.success(request, 'Цитата успешно обновлена')
            return redirect('books:detail', book_id=quote.book.id)
    else:
        form = QuoteForm(instance=quote)
    
    return render(request, 'books/edit_quote.html', {
        'form': form,
        'quote': quote
    })

@login_required
def delete_quote(request, quote_id):
    """Удаление цитаты"""
    quote = get_object_or_404(Quote, id=quote_id)
    
    # Проверяем права на удаление
    if quote.user != request.user:
        messages.error(request, 'У вас нет прав на удаление этой цитаты')
        return redirect('books:detail', book_id=quote.book.id)
    
    if request.method == 'POST':
        book_id = quote.book.id
        quote.delete()
        messages.success(request, 'Цитата успешно удалена')
        return redirect('books:detail', book_id=book_id)
    
    return render(request, 'books/delete_quote.html', {'quote': quote})

@login_required
def edit_review(request, review_id):
    """Редактирование отзыва"""
    review = get_object_or_404(Review, id=review_id)
    
    # Проверяем права на редактирование
    if review.user != request.user:
        messages.error(request, 'У вас нет прав на редактирование этого отзыва')
        return redirect('books:detail', book_id=review.book.id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            
            # Обновляем рейтинг книги
            book = review.book
            book.site_rating = book.reviews.aggregate(Avg('rating'))['rating__avg']
            book.save()
            
            messages.success(request, 'Отзыв успешно обновлен')
            return redirect('books:detail', book_id=review.book.id)
    else:
        form = ReviewForm(instance=review)
    
    return render(request, 'books/edit_review.html', {
        'form': form,
        'review': review
    })

@login_required
def delete_review(request, review_id):
    """Удаление отзыва"""
    review = get_object_or_404(Review, id=review_id)
    
    # Проверяем права на удаление
    if review.user != request.user:
        messages.error(request, 'У вас нет прав на удаление этого отзыва')
        return redirect('books:detail', book_id=review.book.id)
    
    if request.method == 'POST':
        book = review.book
        review.delete()
        
        # Обновляем рейтинг книги
        book.site_rating = book.reviews.aggregate(Avg('rating'))['rating__avg']
        book.save()
        
        messages.success(request, 'Отзыв успешно удален')
        return redirect('books:detail', book_id=book.id)
    
    return render(request, 'books/delete_review.html', {'review': review})

@login_required
def add_quote_from_quotes_page(request):
    """Добавление цитаты со страницы цитат"""
    if request.method == 'POST':
        form = QuoteForm(request.POST)
        book_id = request.POST.get('book')
        
        if form.is_valid() and book_id:
            quote = form.save(commit=False)
            quote.book = get_object_or_404(Book, id=book_id)
            quote.user = request.user
            quote.save()
            
            messages.success(request, 'Цитата успешно добавлена')
            return redirect('books:user_quotes')
        
        messages.error(request, 'Ошибка при добавлении цитаты')
        return redirect('books:user_quotes')
    
    # Получаем список книг пользователя для выбора
    user_books = Book.objects.filter(
        user_relations__user=request.user
    ).distinct().order_by('title')
    
    context = {
        'form': QuoteForm(),
        'user_books': user_books
    }
    return render(request, 'lib/add_quote.html', context)

@login_required
def user_collections(request):
    """Страница пользовательских подборок"""
    user_collections = Collection.objects.filter(
        created_by=request.user
    ).prefetch_related('books').order_by('-created_at')
    
    # Если это AJAX-запрос, возвращаем JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        collections_data = [{
            'id': collection.id,
            'title': collection.title,
            'slug': collection.slug,
            'books_count': collection.books_count,
            'type': collection.get_type_display(),
            'is_public': collection.is_public,
        } for collection in user_collections]
        return JsonResponse({'collections': collections_data})
    
    # Для обычных запросов возвращаем HTML
    context = {
        'user_collections': user_collections,
        'collection_types': Collection.COLLECTION_TYPES,
    }
    return render(request, 'books/collections/user_collections.html', context)

@login_required
def delete_collection(request, slug):
    """Удаление подборки"""
    collection = get_object_or_404(Collection, slug=slug, created_by=request.user)
    
    if request.method == 'POST':
        collection.delete()
        messages.success(request, f'Подборка "{collection.title}" успешно удалена')
        return redirect('books:user_collections')
    
    return render(request, 'books/collections/delete.html', {'collection': collection})

def author_detail(request, author_id):
    """Детальная страница автора"""
    author = get_object_or_404(Author, id=author_id)
    
    # Получаем все книги автора
    books = Book.objects.filter(
        authors=author,
        is_approved=True
    ).select_related('submitted_by').prefetch_related('reviews').order_by('-published_date')
    
    # Пагинация
    paginator = Paginator(books, 12)  # 12 книг на странице
    page_number = request.GET.get('page')
    books = paginator.get_page(page_number)
    
    context = {
        'author': author,
        'books': books,
    }
    
    return render(request, 'books/author_detail.html', context)

def popular_books(request):
    """Страница популярных книг"""
    books = Book.objects.filter(
        is_approved=True
    ).annotate(
        readers_count=Count('user_relations', distinct=True)
    ).filter(
        readers_count__gte=1  # Минимум 1 читатель
    ).order_by('-readers_count')[:100]
    
    context = {
        'books': books,
        'title': 'Топ-100 популярных книг',
        'description': 'Книги, которые чаще всего добавляют в библиотеку'
    }
    return render(request, 'books/collections/books_list.html', context)

def top_rated_books(request):
    """Страница книг с лучшим рейтингом"""
    books = Book.objects.filter(
        is_approved=True
    ).annotate(
        avg_rating=Avg('reviews__rating'),
        reviews_count=Count('reviews')
    ).filter(
        avg_rating__gte=4.0,
        reviews_count__gte=3  # Минимум 3 отзыва для объективности
    ).order_by('-avg_rating', '-reviews_count')[:100]
    
    context = {
        'books': books,
        'title': 'Топ-100 книг по рейтингу',
        'description': 'Книги с самым высоким рейтингом на сайте'
    }
    return render(request, 'books/collections/books_list.html', context)