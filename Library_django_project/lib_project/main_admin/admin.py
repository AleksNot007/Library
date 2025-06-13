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
            'waiting_books': Book.objects.filter(is_approved=False).count(),
            'today': today,
        })
        
        return super().index(request, extra_context)

# Создаем экземпляр кастомного AdminSite
admin_site = LibraryAdminSite(name='admin')

# Регистрируем модели в админке
User = get_user_model()

@admin.register(Book, site=admin_site)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_authors', 'genre', 'pages', 'is_approved', 'submitted_by']
    list_filter = ['is_approved', 'genre']
    search_fields = ['title', 'authors__name', 'submitted_by__username', 'isbn']
    readonly_fields = ['created_at', 'updated_at', 'submitted_by']
    
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
                'isbn'
            ),
            'description': 'Основные характеристики книги'
        }),
        ('Онлайн-источники', {
            'fields': ('online_sources',),
            'description': 'Ссылки на сайты, где можно прочитать книгу онлайн'
        }),
        ('Статус модерации', {
            'fields': ('is_approved', 'moderation_comment'),
            'classes': ('collapse',),
            'description': 'Комментарии пользователя и статус модерации'
        }),
        ('Дополнительно', {
            'fields': (
                'world_rating',
                'submitted_by',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',),
            'description': 'Дополнительная информация о книге'
        }),
    )

    def get_authors(self, obj):
        return ", ".join([author.name for author in obj.authors.all()])
    get_authors.short_description = 'Авторы'

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

# Регистрируем остальные модели
admin_site.register(Author, AuthorAdmin)
admin_site.register(Review, ReviewAdmin)
admin_site.register(UserBookRelation, UserBookRelationAdmin)
admin_site.register(Quote, QuoteAdmin)
admin_site.register(GlobalCollection, GlobalCollectionAdmin)
admin_site.register(User, UserAdmin) 