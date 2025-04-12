from django.contrib import admin
from .models import Book, Author, Review, UserBookRelation

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'display_authors', 'genre')
    search_fields = ('title', 'authors__name', 'genre')
    
    def display_authors(self, obj):
        return ", ".join(author.name for author in obj.authors.all())
    display_authors.short_description = 'Авторы'

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'century', 'country')
    search_fields = ('name', 'country')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('book', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('book__title', 'user__username')

@admin.register(UserBookRelation)
class UserBookRelationAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'list_type', 'added_at')
    list_filter = ('list_type', 'added_at')
    search_fields = ('user__username', 'book__title')
