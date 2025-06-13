from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import json
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.text import slugify

User = get_user_model()

# ----------------------------
# Модель жанра
# ----------------------------
class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название жанра")
    description = models.TextField(blank=True, verbose_name="Описание жанра")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="URL-идентификатор")
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subgenres',
        verbose_name="Родительский жанр"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Жанр"
        verbose_name_plural = "Жанры"
        ordering = ['name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} - {self.name}"
        return self.name

    @property
    def books_count(self):
        """Количество книг в жанре"""
        return self.books.count()

    @property
    def all_subgenres(self):
        """Получить все подчиненные жанры"""
        return self.subgenres.all()


# ----------------------------
# Модель автора
# ----------------------------
from django.db import models

class Author(models.Model):
    name = models.CharField(max_length=255, verbose_name="Имя автора")
    birthday = models.DateField(blank=True, null=True, verbose_name="День рождения")
    die = models.DateField(blank=True, null=True, verbose_name="Дата смерти")
    century = models.PositiveIntegerField(verbose_name="Век")
    country = models.CharField(max_length=255, verbose_name="Страна")
    bio = models.TextField(blank=True, null=True, verbose_name="Биография")
    wiki_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Ссылка на Wikipedia")

    def __str__(self):
        return self.name


class Book(models.Model):
    GENRE_CHOICES = [
        ("fantasy", "Фэнтези"),
        ("sci_fi", "Фантастика"),
        ("thriller_horror", "Триллеры и хорроры"),
        ("detective", "Детективы"),
        ("romance", "Романтика"),
        ("classic", "Классика"),
        ("prose", "Проза"),
        ("history", "История"),
        ("biography", "Биографии и мемуары"),
        ("psychology", "Психология"),
        ("self_help", "Саморазвитие"),
        ("business", "Бизнес"),
        ("health", "Здоровье"),
        ("young_adult", "Young Adult"),
        ("non_fiction", "Нон-фикшн"),
        ("comics", "Комиксы и графические романы"),
        ("children", "Детям"),
        ("audio", "Аудиокнига"),
        ("drama", "Драма"),
        ("other", "Другое")
    ]

    # Основные поля (обязательные)
    title = models.CharField(
        max_length=255, 
        verbose_name='Название',
        help_text='Обязательное поле. Введите название книги.'
    )
    authors = models.ManyToManyField(
        Author, 
        related_name='books', 
        verbose_name='Авторы',
        help_text='Обязательное поле. Выберите одного или нескольких авторов.'
    )
    pages = models.PositiveIntegerField(
        verbose_name='Количество страниц',
        help_text='Обязательное поле. Укажите общее количество страниц в книге.',
        default=1  # Значение по умолчанию
    )

    # Основные поля (опциональные)
    description = models.TextField(
        verbose_name='Описание',
        blank=True,
        help_text='Добавьте описание книги.'
    )
    cover = models.ImageField(
        upload_to='book_covers/', 
        null=True, 
        blank=True, 
        verbose_name='Обложка'
    )
    published_date = models.DateField(
        null=True, 
        blank=True, 
        verbose_name='Дата публикации'
    )
    genre = models.CharField(
        max_length=50, 
        choices=GENRE_CHOICES, 
        default='other', 
        verbose_name='Жанр'
    )
    
    # Рейтинги
    world_rating = models.FloatField(
        null=True, 
        blank=True, 
        verbose_name='Мировой рейтинг'
    )
    site_rating = models.FloatField(
        default=0, 
        verbose_name='Рейтинг на сайте'
    )
    
    # Дополнительная информация
    isbn = models.CharField(
        max_length=13,
        blank=True,
        null=True,
        verbose_name='ISBN',
        help_text='Международный стандартный книжный номер'
    )
    online_sources = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Ссылки для чтения',
        help_text='Укажите ссылки на сайты, где можно прочитать книгу онлайн'
    )
    
    # Служебные поля
    book_id = models.CharField(
        max_length=100, 
        unique=True, 
        blank=True, 
        null=True, 
        verbose_name="Внешний ID книги"
    )
    openlibrary_id = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="ID в OpenLibrary"
    )
    is_approved = models.BooleanField(
        default=False, 
        verbose_name='Одобрено модератором'
    )
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name='Дата добавления'
    )
    updated_at = models.DateTimeField(
        auto_now=True, 
        verbose_name='Дата обновления'
    )
    submitted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='submitted_books', 
        verbose_name='Добавил'
    )
    moderation_comment = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='Комментарий для модератора'
    )
    rejection_reason = models.TextField(
        blank=True, 
        null=True, 
        verbose_name='Причина отклонения'
    )

    class Meta:
        verbose_name = 'Книга'
        verbose_name_plural = 'Книги'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def update_site_rating(self):
        """Обновляет рейтинг книги на сайте на основе пользовательских оценок"""
        avg_rating = self.reviews.aggregate(Avg('rating'))['rating__avg']
        if avg_rating:
            self.site_rating = round(avg_rating, 2)
            self.save(update_fields=['site_rating'])
        return self.site_rating

    @property
    def app_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            return reviews.aggregate(average=Avg('rating'))['average']
        return None

    @property
    def reading_count(self):
        """Количество читающих сейчас"""
        return self.user_relations.filter(list_type='in_progress').count()

    @property
    def finished_count(self):
        """Количество прочитавших"""
        return self.user_relations.filter(list_type='read').count()

    @property
    def want_to_read_count(self):
        """Количество желающих прочитать"""
        return self.user_relations.filter(list_type='want').count()

    def add_online_source(self, name, url):
        """Добавляет ссылку на онлайн-источник для чтения книги"""
        if not isinstance(self.online_sources, dict):
            self.online_sources = {}
        self.online_sources[name] = url
        self.save(update_fields=['online_sources'])

    def remove_online_source(self, name):
        """Удаляет ссылку на онлайн-источник"""
        if isinstance(self.online_sources, dict) and name in self.online_sources:
            del self.online_sources[name]
            self.save(update_fields=['online_sources'])

    def get_online_sources(self):
        """Возвращает все онлайн-источники для чтения"""
        return self.online_sources if isinstance(self.online_sources, dict) else {}


# ----------------------------
# Модель отзыва (от пользователей приложения)
# ----------------------------
class Review(models.Model):
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="reviews",
        to_field='id',
        verbose_name="Книга"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        to_field='id',
        verbose_name="Пользователь"
    )
    # Рейтинг, оставляемый пользователем, от 1 до 5
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Оценка"
    )
    comment = models.TextField(blank=True, null=True, verbose_name="Отзыв")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отзыва")
    spoiler = models.BooleanField(default=False, verbose_name="Содержит спойлер")

    class Meta:
        unique_together = ('book', 'user')
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.rating})"

# ----------------------------
# Определение типов личных списков (коллекций)
# ----------------------------
LIST_TYPE_CHOICES = (
    ('want', 'Хочу прочесть'),
    ('read', 'Прочитано'),
    ('in_progress', 'В процессе'),
    ('stop', 'Стоп-лист'),
    ('favorite', 'Избранное'),
    ('blacklist', 'Черный список'),
    ('recommended', 'Рекомендованные книги'),
)

# ----------------------------
# Промежуточная модель для хранения коллекций книг пользователя
# ----------------------------
class UserBookRelation(models.Model):
    # Ссылка на пользователя (используем кастомную модель)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='book_relations',
        to_field='id',
        verbose_name='Пользователь'
    )
    # Ссылка на книгу
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='user_relations',
        to_field='id',
        verbose_name='Книга'
    )
    # Тип списка, в который добавлена книга
    list_type = models.CharField(max_length=20, choices=LIST_TYPE_CHOICES, verbose_name="Тип списка")
    # Время добавления книги в данный список
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    
    # Прогресс чтения
    progress = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Процент прочитанного"
    )
    progress_pages = models.PositiveIntegerField(
        default=0,
        verbose_name="Количество прочитанных страниц"
    )
    
    # Дополнительные поля
    is_favourite = models.BooleanField(default=False, verbose_name="В избранном")
    notes = models.TextField(blank=True, null=True, verbose_name="Личные заметки")
    comment = models.TextField(blank=True, null=True, verbose_name="Комментарий")

    class Meta:
        # Обеспечивает, что один пользователь не сможет добавить одну и ту же книгу в один и тот же список несколько раз
        unique_together = ('user', 'book', 'list_type')
        verbose_name = "Связь пользователь-книга"
        verbose_name_plural = "Связи пользователь-книга"

    def __str__(self):
        # Метод возвращает строковое представление: имя пользователя, название книги и название списка (через get_list_type_display)
        return f"{self.user.username}: {self.book.title} ({self.get_list_type_display()})"

    def calculate_progress(self):
        """Рассчитывает процент прочитанного на основе прочитанных страниц"""
        if self.book.pages and self.book.pages > 0:
            progress = (self.progress_pages / self.book.pages) * 100
            self.progress = min(round(progress), 100)  # Округляем и ограничиваем 100%
        else:
            self.progress = 0
        return self.progress

    def save(self, *args, **kwargs):
        # Проверяем, нужно ли отслеживать прогресс для данного типа списка
        if self.list_type not in ['in_progress', 'stop']:
            self.progress = 0
            self.progress_pages = 0
        
        # Если книга прочитана, устанавливаем прогресс в 100%
        if self.list_type == 'read':
            self.progress = 100
            if self.book.pages:  # если известно количество страниц
                self.progress_pages = self.book.pages
        else:
            # Для читаемых книг и стоп-листа считаем процент
            self.progress = self.calculate_progress()
        
        super().save(*args, **kwargs)

# ----------------------------
# Модель цитаты
# ----------------------------
class Quote(models.Model):
    """Модель для хранения цитат из книг"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quotes",
        to_field='id',
        verbose_name="Пользователь"
    )
    book = models.ForeignKey(
        'Book',
        on_delete=models.CASCADE,
        related_name="quotes",
        to_field='id',
        verbose_name="Книга"
    )
    text = models.TextField(verbose_name="Текст цитаты")
    page = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Номер страницы"
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name="Публичная цитата",
        help_text="Если отмечено, цитата будет видна на странице книги"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    class Meta:
        verbose_name = "Цитата"
        verbose_name_plural = "Цитаты"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['book', 'is_public']),
            models.Index(fields=['user', 'created_at'])
        ]

    def __str__(self):
        return f"{self.book.title} - {self.text[:50]}..."

    @property
    def short_text(self):
        """Возвращает сокращенный текст цитаты для отображения в списках"""
        return f"{self.text[:100]}..." if len(self.text) > 100 else self.text

class GlobalCollection(models.Model):
    title = models.CharField(max_length=255, verbose_name="Название коллекции")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    books = models.ManyToManyField(Book, related_name="global_collections", verbose_name="Книги")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_active = models.BooleanField(default=True, verbose_name="Активна")

    class Meta:
        verbose_name = "Глобальная коллекция"
        verbose_name_plural = "Глобальные коллекции"

    def __str__(self):
        return self.title

def add_book_from_openlibrary(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        results = external_book_search(title)
        # Обработка результатов и создание книги
        return redirect('books:book_list')
    return render(request, 'books/add_book.html')

class Collection(models.Model):
    """Модель для подборок книг"""
    COLLECTION_TYPES = [
        ('custom', 'Пользовательская'),
        ('genre', 'По жанру'),
        ('author', 'По автору'),
        ('theme', 'Тематическая'),
        ('period', 'По периоду'),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name='Название'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    cover = models.ImageField(
        upload_to='collection_covers/',
        blank=True,
        null=True,
        verbose_name='Обложка'
    )
    type = models.CharField(
        max_length=20,
        choices=COLLECTION_TYPES,
        default='custom',
        verbose_name='Тип подборки'
    )
    slug = models.SlugField(
        'URL',
        unique=True,
        help_text='Уникальный идентификатор для URL'
    )
    is_public = models.BooleanField(
        default=True,
        verbose_name='Публичная',
        help_text='Если отмечено, подборка будет видна всем пользователям'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='collections',
        to_field='id',
        verbose_name='Создатель'
    )
    books = models.ManyToManyField(
        'Book',
        related_name='collections',
        verbose_name='Книги',
        db_column='book_id'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Подборка'
        verbose_name_plural = 'Подборки'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', 'is_public']),
            models.Index(fields=['type', 'created_at'])
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('books:collection_detail', kwargs={'slug': self.slug})

    @property
    def books_count(self):
        """Возвращает количество книг в подборке"""
        return self.books.count()

    def increment_views(self):
        self.views_count += 1
        self.save()

    def save(self, *args, **kwargs):
        """Ensure slug is created from title if not provided"""
        if not self.slug:
            self.slug = slugify(self.title)
            # Make slug unique
            base_slug = self.slug
            counter = 1
            while Collection.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

@receiver(post_save, sender='books.Review')
def update_book_rating(sender, instance, **kwargs):
    """
    Сигнал для автоматического обновления рейтинга книги при сохранении отзыва
    """
    instance.book.update_site_rating()
