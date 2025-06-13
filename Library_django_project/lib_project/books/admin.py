from django.contrib import admin
from django.urls import path
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from .models import Book, Author, Review, UserBookRelation, Quote, GlobalCollection, Collection, Genre
from users.models import ModeratorMessage
from . import views
from django.utils.html import format_html
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.safestring import mark_safe

class LibraryAdminSite(admin.AdminSite):
    site_header = 'Библиотека - Административная панель'
    site_title = 'Библиотека'
    index_title = 'Управление библиотекой'
    index_template = 'admin/index.html'
    app_index_template = 'admin/index.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('statistics/', self.admin_view(views.site_statistics), name='site_statistics'),
        ]
        return custom_urls + urls
    
    def index(self, request, extra_context=None):
        """Переопределяем метод index для добавления статистики на главную страницу"""
        if extra_context is None:
            extra_context = {}
            
        User = get_user_model()
        today = timezone.now().date()
        
        # Добавляем базовую статистику
        extra_context.update({
            'book_count': Book.objects.count(),
            'user_count': User.objects.count(),
            'author_count': Author.objects.count(),
            'review_count': Review.objects.count(),
            'waiting_books': Book.objects.filter(is_approved=False).count(),
            'today': today,
        })
        
        return super().index(request, extra_context)

# Создаем экземпляр кастомного AdminSite
admin_site = LibraryAdminSite(name='admin')

# Получаем модель User
User = get_user_model()

class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'get_authors', 'genre', 'pages', 'is_approved', 'site_rating', 'created_at')
    list_filter = ('is_approved', 'genre', 'created_at')
    search_fields = ('title', 'authors__name', 'submitted_by__username', 'description', 'isbn')
    readonly_fields = (
        'submitted_by', 
        'created_at', 
        'updated_at', 
        'book_link', 
        'site_rating', 
        'app_rating',
        'reading_count', 
        'finished_count', 
        'want_to_read_count'
    )
    actions = ['approve_books', 'reject_books']
    
    fieldsets = (
        ('Основная информация', {
            'fields': (
                'title',
                'authors',
                'pages',
                'genre',
                'description',
                'cover',
                'published_date',
                'isbn',
            ),
            'classes': ('wide',),
            'description': 'Основные характеристики книги'
        }),
        ('Онлайн-источники', {
            'fields': (
                'online_sources',
            ),
            'description': 'Ссылки на сайты, где можно прочитать книгу онлайн'
        }),
        ('Рейтинги и статистика', {
            'fields': (
                'world_rating',
                'site_rating',
                'app_rating',
                ('reading_count', 'finished_count', 'want_to_read_count')
            ),
            'classes': ('collapse',),
            'description': 'Рейтинги и статистика чтения'
        }),
        ('Статус модерации', {
            'fields': (
                'is_approved',
                'moderation_comment',
                'rejection_reason',
                'book_link'
            ),
            'classes': ('collapse',),
            'description': 'Управление статусом модерации книги'
        }),
        ('Идентификаторы', {
            'fields': (
                'book_id',
                'openlibrary_id',
            ),
            'classes': ('collapse',),
            'description': 'Внешние идентификаторы книги'
        }),
        ('Служебная информация', {
            'fields': (
                'submitted_by',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',),
            'description': 'Служебные поля'
        }),
    )

    def get_authors(self, obj):
        return ", ".join([author.name for author in obj.authors.all()])
    get_authors.short_description = 'Авторы'

    def book_link(self, obj):
        if obj and obj.is_approved:
            url = reverse('books:detail', args=[obj.id])
            return mark_safe(f'<a href="{url}" target="_blank">Перейти к странице книги</a>')
        return '-'
    book_link.short_description = 'Ссылка на книгу'

    def moderation_status(self, obj):
        if obj.is_approved:
            return format_html('<span style="color: green;">✓ Одобрено</span>')
        return format_html('<span style="color: red;">✗ На модерации</span>')
    moderation_status.short_description = 'Статус модерации'

    def save_model(self, request, obj, form, change):
        is_new = not obj.pk
        old_status = None if is_new else Book.objects.get(pk=obj.pk).is_approved
        
        if not is_new:
            old_obj = Book.objects.get(pk=obj.pk)
            status_changed = old_obj.is_approved != obj.is_approved
        else:
            status_changed = obj.is_approved

        if not obj.is_approved:
            # Сохраняем данные для сообщения перед удалением
            title = obj.title
            submitted_by = obj.submitted_by
            
            # Создаем сообщение для пользователя
            ModeratorMessage.objects.create(
                user=submitted_by,
                message_type='book_rejected',
                message=f'Ваша книга "{title}" была отклонена. Пожалуйста, проверьте правильность '
                       f'введенных данных и попробуйте добавить книгу еще раз.'
            )
            
            # Удаляем книгу
            if not is_new:  # Только если книга уже существует
                obj.delete()
            messages.warning(request, f'Книга "{title}" отклонена и удалена')
            return  # Прерываем сохранение

        # Если книга одобрена, сохраняем её
        super().save_model(request, obj, form, change)

        if status_changed and obj.is_approved:
            # Книга была одобрена
            book_url = reverse('books:detail', args=[obj.id])
            ModeratorMessage.objects.create(
                user=obj.submitted_by,
                book=obj,
                message_type='book_approved',
                message=mark_safe(f'Ваша книга "{obj.title}" была одобрена! '
                                f'<a href="{book_url}">Перейти к странице книги</a>')
            )
            messages.success(request, f'Книга "{obj.title}" успешно одобрена')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('submitted_by').prefetch_related('authors')

    def changelist_view(self, request, extra_context=None):
        if not extra_context:
            extra_context = {}
        
        extra_context.update({
            'total_books': Book.objects.count(),
            'waiting_books': Book.objects.filter(is_approved=False).count(),
            'approved_books': Book.objects.filter(is_approved=True).count(),
            'rejected_books': Book.objects.filter(is_approved=False).count(),
        })
        
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reject-books/', self.reject_books_view, name='reject-books'),
        ]
        return custom_urls + urls

    def reject_books_view(self, request):
        if request.method == 'POST':
            book_ids = request.POST.getlist('_selected_action')
            rejection_reason = request.POST.get('rejection_reason')
            
            if not rejection_reason:
                self.message_user(request, 'Необходимо указать причину отклонения', level=messages.ERROR)
                return redirect('..')
            
            books = Book.objects.filter(id__in=book_ids)
            for book in books:
                book.is_approved = False
                book.save()
                
                # Создаем сообщение для пользователя
                ModeratorMessage.objects.create(
                    user=book.submitted_by,
                    book=book,
                    message_type='book_rejected',
                    message=f'Ваша книга "{book.title}" была отклонена по следующей причине:\n{rejection_reason}'
                )
            
            self.message_user(request, f'Успешно отклонено книг: {len(books)}')
            return redirect('..')
            
        context = {
            'title': 'Отклонение книг',
            'books': Book.objects.filter(id__in=request.GET.getlist('ids')),
        }
        return TemplateResponse(request, 'admin/reject_books.html', context)

    def approve_book(self, request, queryset):
        """Одобрение книги модератором"""
        for book in queryset:
            book.is_approved = True
            book.save()
            
            # Создаем сообщение для пользователя
            ModeratorMessage.objects.create(
                user=book.submitted_by,
                book=book,
                message_type='book_approved',
                message=f'Ваша книга "{book.title}" была одобрена и добавлена в каталог. '
                        f'<a href="{reverse("books:detail", args=[book.id])}">Перейти к книге</a>'
            )

class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'century', 'country', 'books_count')
    list_filter = ('century', 'country')
    search_fields = ('name', 'country', 'bio')
    readonly_fields = ('books_count',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'birthday', 'die', 'century', 'country')
        }),
        ('Дополнительно', {
            'fields': ('bio', 'wiki_url', 'books_count')
        }),
    )
    
    def books_count(self, obj):
        return obj.books.count()
    books_count.short_description = 'Количество книг'

class ReviewAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'rating', 'created_at', 'has_spoiler')
    list_filter = ('rating', 'created_at', 'spoiler')
    search_fields = ('book__title', 'user__username', 'comment')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Основное', {
            'fields': ('book', 'user', 'rating')
        }),
        ('Содержание', {
            'fields': ('comment', 'spoiler')
        }),
        ('Мета', {
            'fields': ('created_at',)
        }),
    )

    def has_spoiler(self, obj):
        return '⚠️ Есть' if obj.spoiler else '✓ Нет'
    has_spoiler.short_description = 'Спойлер'

class UserBookRelationAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'list_type', 'progress', 'is_favourite', 'added_at')
    list_filter = ('list_type', 'is_favourite', 'added_at')
    search_fields = ('user__username', 'book__title', 'notes')
    readonly_fields = ('added_at',)
    fieldsets = (
        ('Основное', {
            'fields': ('user', 'book', 'list_type', 'is_favourite')
        }),
        ('Прогресс', {
            'fields': ('progress', 'progress_pages')
        }),
        ('Дополнительно', {
            'fields': ('notes', 'comment', 'added_at')
        }),
    )

class QuoteAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'short_text', 'is_public', 'created_at')
    list_filter = ('is_public', 'created_at')
    search_fields = ('book__title', 'user__username', 'text')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Основное', {
            'fields': ('book', 'user', 'text', 'page')
        }),
        ('Настройки', {
            'fields': ('is_public', 'created_at')
        }),
    )

    def short_text(self, obj):
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
    short_text.short_description = 'Текст цитаты'

class CollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'created_by', 'is_public', 'books_count', 'created_at')
    list_filter = ('type', 'is_public', 'created_at')
    search_fields = ('title', 'description', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'books_count')
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        ('Основное', {
            'fields': ('title', 'slug', 'description', 'type', 'is_public')
        }),
        ('Содержимое', {
            'fields': ('books', 'cover')
        }),
        ('Мета', {
            'fields': ('created_by', 'created_at', 'updated_at', 'books_count')
        }),
    )

    def books_count(self, obj):
        return obj.books.count()
    books_count.short_description = 'Количество книг'

class GlobalCollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'books_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'books_count')
    fieldsets = (
        ('Основное', {
            'fields': ('title', 'description', 'is_active')
        }),
        ('Книги', {
            'fields': ('books', 'books_count')
        }),
        ('Мета', {
            'fields': ('created_at',)
        }),
    )

    def books_count(self, obj):
        return obj.books.count()
    books_count.short_description = 'Количество книг'

class GenreAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'books_count', 'created_at')
    list_filter = ('parent', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'books_count')
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        ('Основное', {
            'fields': ('name', 'slug', 'description', 'parent')
        }),
        ('Мета', {
            'fields': ('created_at', 'updated_at', 'books_count')
        }),
    )

    def books_count(self, obj):
        return obj.books_count
    books_count.short_description = 'Количество книг'

# Регистрируем все модели только в кастомном админ-сайте
admin_site.register(Book, BookAdmin)
admin_site.register(Author, AuthorAdmin)
admin_site.register(Review, ReviewAdmin)
admin_site.register(UserBookRelation, UserBookRelationAdmin)
admin_site.register(Quote, QuoteAdmin)
admin_site.register(Collection, CollectionAdmin)
admin_site.register(GlobalCollection, GlobalCollectionAdmin)
admin_site.register(Genre, GenreAdmin)
                                           