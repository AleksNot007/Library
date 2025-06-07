from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Count, Avg, Q, Case, When, IntegerField, Value
from django.contrib import messages
from django.http import JsonResponse
from .models import Book, Author, Review, UserBookRelation, Quote, Collection
from .forms import OpenLibrarySearchForm
import requests
from datetime import datetime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.files.temp import NamedTemporaryFile
from django.core.files import File
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from urllib.parse import quote
import re
from django.utils.text import slugify
from django.http import Http404

def home(request):
    """Главная страница"""
    # Получаем популярные книги
    popular_books = Book.objects.filter(
        is_approved=True
    ).select_related('submitted_by').prefetch_related('authors').order_by('-id')[:4]
    
    # Получаем рекомендованные книги для авторизованного пользователя
    recommended_books = []
    if request.user.is_authenticated:
        # Получаем жанры, которые пользователь уже читал
        user_genres = Book.objects.filter(
            user_relations__user=request.user
        ).values_list('genre', flat=True).distinct()
        
        # Получаем книги из тех же жанров, которые пользователь еще не читал
        recommended_books = Book.objects.filter(
            genre__in=user_genres,
            is_approved=True
        ).exclude(
            user_relations__user=request.user
        ).select_related('submitted_by').prefetch_related('authors').order_by('?')[:4]
    
    context = {
        'popular_books': popular_books,
        'recommended_books': recommended_books,
        'GENRE_CHOICES': Book.GENRE_CHOICES,
    }
    return render(request, 'books/home.html', context)

def catalog(request):
    """Общий каталог всех книг библиотеки"""
    genre = request.GET.get('genre')
    ordering = request.GET.get('ordering', 'title')
    page_number = request.GET.get('page', 1)

    # Показываем только одобренные книги в каталоге
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

    context = {
        'reading_now': reading_now,
        'want_to_read': want_to_read,
        'finished': finished,
        'favorites': favorites,
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
    
    if query:
        # Разбиваем поисковый запрос на слова
        search_words = query.split()
        
        # Сначала ищем точное совпадение (все слова должны быть в названии)
        exact_match_query = Q()
        for word in search_words:
            exact_match_query &= Q(title__icontains=word)
        
        exact_matches = Book.objects.filter(
            exact_match_query & Q(is_approved=True)
        ).distinct().select_related('submitted_by').prefetch_related('authors')

        # Если точных совпадений нет, ищем частичные совпадения
        if not exact_matches.exists():
            # Создаем Q-объект для поиска частичных совпадений
            partial_match_query = Q()
            relevance_cases = []
            
            for word in search_words:
                word_query = Q(title__icontains=word)
                partial_match_query |= word_query
                # Добавляем Case для подсчета совпадений каждого слова
                relevance_cases.append(
                    Case(
                        When(title__icontains=word, then=1),
                        default=0,
                        output_field=IntegerField(),
                    )
                )
            
            similar_books = Book.objects.filter(
                (partial_match_query | 
                Q(authors__name__icontains=query) |
                Q(genre__icontains=query)) &
                Q(is_approved=True)
            ).annotate(
                # Считаем релевантность как сумму совпадений слов
                relevance=sum(relevance_cases)
            ).distinct().select_related('submitted_by').prefetch_related('authors').order_by('-relevance', 'title')

            context = {
                'books': similar_books,
                'query': query,
                'no_exact_match': True,
                'no_results': not similar_books.exists(),
            }
        else:
            context = {
                'books': exact_matches,
                'query': query,
                'no_exact_match': False,
                'no_results': False,
            }
    else:
        # Если нет запроса, показываем последние добавленные книги
        books = Book.objects.filter(
            is_approved=True
        ).order_by('-created_at')[:10]
        
        context = {
            'books': books,
            'query': query,
            'no_exact_match': False,
            'no_results': False,
        }
    
    return render(request, 'books/search.html', context)

def book_detail(request, book_id):
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

def collection_detail(request, collection_type, genre=None):
    """Детальная страница подборки"""
    if collection_type == 'genre' and genre:
        # Создаем словарь для преобразования русских названий в коды
        genre_name_to_code = {name: code for code, name in Book.GENRE_CHOICES}
        
        # Если передано русское название жанра, получаем его код
        genre_code = genre_name_to_code.get(genre, genre)
        
        # Получаем топ книг конкретного жанра
        books = Book.objects.filter(
            genre=genre_code,
            is_approved=True
        ).annotate(
            avg_rating=Avg('reviews__rating'),
            readers_count=Count('user_relations', distinct=True)
        ).filter(
            avg_rating__gte=4.5
        ).order_by('-avg_rating', '-readers_count')[:100]
        
        # Получаем русское название жанра из кода
        genre_display_name = dict(Book.GENRE_CHOICES).get(genre_code, genre_code)
        title = f"Топ-100 книг жанра {genre_display_name}"
        
    elif collection_type == 'popular':
        # Получаем популярные книги
        total_users = get_user_model().objects.count()
        books = Book.objects.filter(
            is_approved=True
        ).annotate(
            readers_count=Count('user_relations', distinct=True)
        ).filter(
            readers_count__gte=total_users * 0.3
        ).order_by('-readers_count')[:100]
        
        title = "Самые популярные книги"
        
    elif collection_type == 'top_rated':
        # Получаем топ по рейтингу
        books = Book.objects.filter(
            is_approved=True
        ).annotate(
            avg_rating=Avg('reviews__rating'),
            reviews_count=Count('reviews')
        ).filter(
            avg_rating__gte=4.5,
            reviews_count__gte=5
        ).order_by('-avg_rating', '-reviews_count')[:100]
        
        title = "Топ-100 книг по рейтингу"
        
    elif collection_type == 'most_added':
        # Получаем часто добавляемые книги
        books = Book.objects.filter(
            is_approved=True
        ).annotate(
            total_adds=Count('user_relations')
        ).order_by('-total_adds')[:100]
        
        title = "Часто добавляемые книги"
        
    else:
        raise Http404("Подборка не найдена")

    # Пагинация
    paginator = Paginator(books, 12)  # 12 книг на странице
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': title,
        'books': page_obj,
        'collection_type': collection_type,
        'genre': genre,
    }
    return render(request, 'books/collections/detail.html', context)

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
def add_book_to_collection(request, collection_slug, book_id):
    """Добавление книги в подборку"""
    collection = get_object_or_404(Collection, slug=collection_slug)
    book = get_object_or_404(Book, id=book_id)
    
    # Проверяем права на редактирование
    if collection.created_by != request.user and not request.user.is_staff:
        return JsonResponse({
            'status': 'error',
            'message': 'У вас нет прав на редактирование этой подборки'
        }, status=403)
    
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
def search_openlibrary(request):
    """Поиск книг в Open Library"""
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

    return render(request, 'books/openlibrary_search.html', {
        'results': page_obj,
        'query': query,
        'selected_language': language,
        'language_choices': language_choices,
    })

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

@login_required
def add_book_from_openlibrary(request):
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
            author_name = book_data.get('author', 'Unknown Author')
            author, _ = Author.objects.get_or_create(
                name=author_name,
                defaults={
                    'century': century or 20,  # Если век не определен, используем 20-й
                    'country': book_data.get('author_country', 'Неизвестно')
                }
            )

            # Определяем статус модерации на основе полноты данных
            is_complete = all([
                book_data.get('title'),
                book_data.get('author'),
                book_data.get('first_publish_year'),
                book_data.get('description'),
                book_data.get('cover_i')
            ])
            
            # Создаем книгу
            book = Book.objects.create(
                title=book_data.get('title', 'Без названия').strip(),
                description=book_data.get('description', '').strip() or 'Описание отсутствует',
                published_date=published_date,
                world_rating=None,
                is_approved=False,  # Книга всегда требует одобрения модератора
                needs_moderation=not is_complete,  # Если данные неполные, требуется проверка модератором
                submitted_by=request.user,
                genre=book_data.get('genre', 'other')  # Значение по умолчанию
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
            
            # Формируем сообщение в зависимости от полноты данных
            if is_complete:
                message = f'Книга "{book.title}" добавлена и ожидает одобрения модератора.'
            else:
                message = (
                    f'Книга "{book.title}" добавлена, но требует дополнительной проверки '
                    'из-за неполных данных. Модератор дополнит недостающую информацию.'
                )
            
            messages.success(request, message)
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
            title = request.POST.get('title')
            author_name = request.POST.get('author')
            genre = request.POST.get('genre')

            if not all([title, author_name, genre]):
                messages.error(
                    request,
                    'Пожалуйста, заполните все обязательные поля: название, автор и жанр.'
                )
                return redirect('books:add_book')

            # Создаем или получаем автора
            author, _ = Author.objects.get_or_create(
                name=author_name,
                defaults={
                    'century': 20,  # Значение по умолчанию
                    'country': 'Неизвестно'
                }
            )
            
            # Создаем книгу
            book = Book.objects.create(
                title=title.strip(),
                description=request.POST.get('description', '').strip(),
                published_date=request.POST.get('published_date') or None,
                genre=genre,
                is_approved=False,  # Новая книга по умолчанию не одобрена
                needs_moderation=True,  # Требуется модерация
                submitted_by=request.user
            )
            
            # Добавляем автора к книге
            book.authors.add(author)
            
            # Обрабатываем загруженную обложку
            if request.FILES.get('cover'):
                book.cover = request.FILES['cover']
                book.save()
            
            messages.info(
                request, 
                f'Книга "{book.title}" добавлена и ожидает проверки модератором. '
                'После одобрения вы сможете добавить её в свою личную библиотеку.'
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

@login_required
@require_http_methods(["GET", "POST"])
@ensure_csrf_cookie
def add_to_list(request, book_id, list_type):
    """Добавление книги в список пользователя"""
    print(f"Received request: {request.method} {request.path}")
    print(f"Book ID: {book_id}, List Type: {list_type}")
    print(f"User: {request.user.username}")
    print(f"Headers: {dict(request.headers)}")
    
    try:
        # Проверяем допустимость типа списка
        valid_list_types = ['want', 'read', 'in_progress', 'stop', 'favorite', 'blacklist', 'none']
        if list_type not in valid_list_types:
            print(f"Invalid list type: {list_type}")
            return JsonResponse({
                'status': 'error',
                'message': f'Недопустимый тип списка: {list_type}'
            }, status=400)

        # Проверяем существование книги
        try:
            book = Book.objects.get(id=book_id)
            print(f"Found book: {book.title} (ID: {book.id})")
        except Book.DoesNotExist:
            print(f"Book not found: {book_id}")
            return JsonResponse({
                'status': 'error',
                'message': 'Книга не найдена'
            }, status=404)
        
        # Проверяем, одобрена ли книга
        if not book.is_approved and list_type != 'none':
            print(f"Book not approved: {book.title}")
            return JsonResponse({
                'status': 'error',
                'message': 'Книга ожидает одобрения модератора'
            }, status=400)
        
        # Словарь для перевода типов списков
        list_type_display = {
            'want': 'Хочу прочесть',
            'read': 'Прочитано',
            'in_progress': 'Читаю сейчас',
            'stop': 'Стоп-лист',
            'favorite': 'Избранное',
            'blacklist': 'Черный список',
            'none': 'Не в списке'
        }

        # Получаем текущее отношение пользователь-книга
        user_relation = UserBookRelation.objects.filter(
            user=request.user,
            book=book
        ).first()
        print(f"Current relation: {user_relation.list_type if user_relation else 'None'}")

        # Если тип списка 'none', удаляем отношение
        if list_type == 'none':
            if user_relation:
                old_list_type = user_relation.list_type
                user_relation.delete()
                print(f"Removed book from list: {old_list_type}")
                return JsonResponse({
                    'status': 'success',
                    'message': f'Книга удалена из списка "{list_type_display[old_list_type]}"',
                    'action': 'removed'
                })
            print("Book was not in any list")
            return JsonResponse({
                'status': 'success',
                'message': 'Книга не находилась ни в одном списке',
                'action': 'none'
            })

        # Обработка добавления/изменения списка
        if user_relation:
            if user_relation.list_type == list_type:
                # Если книга уже в этом списке, удаляем её оттуда
                user_relation.delete()
                print(f"Removed book from list: {list_type}")
                return JsonResponse({
                    'status': 'success',
                    'message': f'Книга удалена из списка "{list_type_display[list_type]}"',
                    'action': 'removed'
                })
            else:
                # Если книга в другом списке, обновляем тип
                old_list_type = user_relation.list_type
                user_relation.list_type = list_type
                user_relation.save()
                print(f"Moved book from {old_list_type} to {list_type}")
                return JsonResponse({
                    'status': 'success',
                    'message': f'Книга перемещена из "{list_type_display[old_list_type]}" в "{list_type_display[list_type]}"',
                    'action': 'moved'
                })
        else:
            # Создаем новую связь
            UserBookRelation.objects.create(
                user=request.user,
                book=book,
                list_type=list_type
            )
            print(f"Added book to list: {list_type}")
            return JsonResponse({
                'status': 'success',
                'message': f'Книга добавлена в список "{list_type_display[list_type]}"',
                'action': 'added'
            })
            
    except Exception as e:
        import traceback
        print(f"Error in add_to_list: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'status': 'error',
            'message': f'Произошла ошибка при обработке запроса: {str(e)}'
        }, status=500)

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
def add_review(request, book_id):
    """Добавление отзыва к книге"""
    if request.method == 'POST':
        try:
            book = get_object_or_404(Book, id=book_id)
            
            # Проверяем, не оставлял ли пользователь уже отзыв
            existing_review = Review.objects.filter(user=request.user, book=book).first()
            if existing_review:
                messages.warning(request, 'Вы уже оставляли отзыв к этой книге')
                return redirect('books:detail', book_id=book_id)
            
            # Получаем данные из формы
            rating = int(request.POST.get('rating', 0))
            comment = request.POST.get('text', '').strip()
            
            # Проверяем валидность данных
            if not (1 <= rating <= 5):
                messages.error(request, 'Оценка должна быть от 1 до 5')
                return redirect('books:detail', book_id=book_id)
            
            if not comment:
                messages.error(request, 'Текст отзыва не может быть пустым')
                return redirect('books:detail', book_id=book_id)
            
            # Создаем отзыв
            Review.objects.create(
                user=request.user,
                book=book,
                rating=rating,
                comment=comment
            )
            
            messages.success(request, 'Отзыв успешно добавлен')
            
        except Exception as e:
            messages.error(request, f'Произошла ошибка при добавлении отзыва: {str(e)}')
        
        return redirect('books:detail', book_id=book_id)
    
    return redirect('books:detail', book_id=book_id)

def search_books(request):
    query = request.GET.get('q', '')
    genre = request.GET.get('genre', '')
    ordering = request.GET.get('ordering', 'title')
    
    books = Book.objects.all()
    no_results = False
    
    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(authors__name__icontains=query) |
            Q(genre__icontains=query) |
            Q(description__icontains=query)
        ).distinct()
        no_results = not books.exists()
    
    if genre:
        books = books.filter(genre=genre)
    
    # Применяем сортировку
    if ordering == '-published_date':
        books = books.order_by('-published_date')
    elif ordering == 'published_date':
        books = books.order_by('published_date')
    elif ordering == 'rating':
        books = books.order_by('-average_rating')
    elif ordering == 'popularity':
        books = books.order_by('-views_count')
    else:  # default sorting by title
        books = books.order_by('title')
    
    # Пагинация
    paginator = Paginator(books, 12)  # 12 книг на странице
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'books': page_obj,
        'query': query,
        'selected_genre': genre,
        'selected_ordering': ordering,
        'GENRE_CHOICES': Book.GENRE_CHOICES,
        'no_results': no_results
    }
    
    return render(request, 'books/catalog.html', context)