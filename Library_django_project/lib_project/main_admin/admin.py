from django.contrib import admin
from django.urls import path
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from books.models import Book, Author, Review, UserBookRelation, Quote, GlobalCollection
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
admin_site = LibraryAdminSite(name='library_admin')

# Регистрируем модели в админке
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'display_authors', 'genre', 'is_approved', 'needs_moderation', 'submitted_by', 'submission_date')
    list_filter = ('genre', 'is_approved', 'needs_moderation')
    search_fields = ('title', 'authors__name', 'genre')
    actions = ['approve_books', 'reject_books']
    readonly_fields = ('submitted_by', 'submission_date')

    def display_authors(self, obj):
        return ", ".join(author.name for author in obj.authors.all())
    display_authors.short_description = 'Авторы'

    def submission_date(self, obj):
        return obj.created_at
    submission_date.short_description = 'Дата добавления'

    def approve_books(self, request, queryset):
        updated = queryset.update(is_approved=True, needs_moderation=True)
        self.message_user(request, f'{updated} книг успешно одобрено и добавлено в каталог.')
    approve_books.short_description = 'Одобрить и добавить в каталог'

    def reject_books(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} книг отправлено на рассмотрение модератором.', messages.WARNING)
    reject_books.short_description = 'Отправить на рассмотрение'

    def changelist_view(self, request, extra_context=None):
        if not extra_context:
            extra_context = {}
        
        extra_context.update({
            'total_books': Book.objects.count(),
            'waiting_books': Book.objects.filter(is_approved=False, needs_moderation=True).count(),  # Книги на рассмотрении
            'approved_books': Book.objects.filter(is_approved=True, needs_moderation=True).count(),  # Одобренные книги
            'rejected_books': Book.objects.filter(is_approved=False, needs_moderation=False).count(),  # Отклоненные книги
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
    list_filter = ('list_type', 'added_at')
    search_fields = ('user__username', 'book__title')

class QuoteAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'text', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('text', 'book__title', 'user__username')

class GlobalCollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title',)

# Регистрируем все модели
admin_site.register(Book, BookAdmin)
admin_site.register(Author, AuthorAdmin)
admin_site.register(Review, ReviewAdmin)
admin_site.register(UserBookRelation, UserBookRelationAdmin)
admin_site.register(Quote, QuoteAdmin)
admin_site.register(GlobalCollection, GlobalCollectionAdmin)

# Регистрируем пользователей
User = get_user_model()
admin_site.register(User, UserAdmin) 