from django.contrib import admin
from django.urls import path
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from .models import Book, Author, Review, UserBookRelation, Quote, GlobalCollection
from . import views

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
            'waiting_books': Book.objects.filter(needs_moderation=True).count(),
            'today': today,
        })
        
        return super().index(request, extra_context)

# Создаем экземпляр кастомного AdminSite
admin_site = LibraryAdminSite(name='admin')  # Изменяем name на 'admin'

# Получаем модель User
User = get_user_model()

class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'display_authors', 'genre', 'is_approved', 'needs_moderation', 'submitted_by', 'submission_date')
    list_filter = ('genre', 'is_approved', 'needs_moderation')
    search_fields = ('title', 'authors__name', 'genre')
    actions = ['approve_books', 'reject_books']
    readonly_fields = ('submitted_by', 'submission_date')
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'authors', 'genre', 'description', 'published_date', 'cover')
        }),
        ('Статус модерации', {
            'fields': ('is_approved', 'needs_moderation', 'submitted_by', 'submission_date'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('submitted_by')

    def display_authors(self, obj):
        return ", ".join(author.name for author in obj.authors.all())
    display_authors.short_description = 'Авторы'

    def submission_date(self, obj):
        return obj.created_at
    submission_date.short_description = 'Дата добавления'

    def approve_books(self, request, queryset):
        updated = queryset.update(is_approved=True, needs_moderation=False)
        self.message_user(request, f'Одобрено {updated} книг.')
    approve_books.short_description = 'Одобрить выбранные книги'

    def reject_books(self, request, queryset):
        updated = queryset.update(is_approved=False, needs_moderation=False)
        self.message_user(
            request, 
            f'Отклонено {updated} книг. Пользователи получат уведомление о необходимости проверить данные.',
            messages.WARNING
        )
    reject_books.short_description = 'Отклонить выбранные книги'

    def changelist_view(self, request, extra_context=None):
        if not extra_context:
            extra_context = {}
        
        # Добавляем статистику по книгам
        extra_context.update({
            'total_books': Book.objects.count(),
            'waiting_books': Book.objects.filter(needs_moderation=True).count(),
            'approved_books': Book.objects.filter(is_approved=True).count(),
            'rejected_books': Book.objects.filter(is_approved=False, needs_moderation=False).count(),
        })
        
        return super().changelist_view(request, extra_context=extra_context)

class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'century', 'country')
    search_fields = ('name', 'country')

class ReviewAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('book__title', 'user__username')

class UserBookRelationAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'list_type', 'added_at')
    list_filter = ('list_type', 'added_at', 'user')
    search_fields = ('user__username', 'book__title')

    def changelist_view(self, request, extra_context=None):
        if not extra_context:
            extra_context = {}
        
        # Подсчет книг по пользователям
        user_stats = get_user_model().objects.annotate(
            total_books=Count('book_relations')
        ).values('username', 'total_books')
        
        # Подсчет книг по типам списков для каждого пользователя
        list_stats = UserBookRelation.objects.values(
            'user__username', 'list_type'
        ).annotate(
            count=Count('book')
        ).order_by('user__username', 'list_type')

        extra_context['user_stats'] = user_stats
        extra_context['list_stats'] = list_stats
        
        return super().changelist_view(request, extra_context=extra_context)

class QuoteAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'short_text', 'is_public', 'created_at', 'likes_count')
    list_filter = ('is_public', 'created_at', 'book')
    search_fields = ('text', 'book__title', 'user__username')
    raw_id_fields = ('book', 'user')
    readonly_fields = ('created_at', 'likes_count')

    def short_text(self, obj):
        return obj.short_text
    short_text.short_description = "Текст цитаты"

class GlobalCollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title',)
    list_editable = ('is_active',)
    list_per_page = 10

# Регистрируем все модели в кастомном админ-сайте
admin_site.register(Book, BookAdmin)
admin_site.register(Author, AuthorAdmin)
admin_site.register(Review, ReviewAdmin)
admin_site.register(UserBookRelation, UserBookRelationAdmin)
admin_site.register(Quote, QuoteAdmin)
admin_site.register(GlobalCollection, GlobalCollectionAdmin)
                                           