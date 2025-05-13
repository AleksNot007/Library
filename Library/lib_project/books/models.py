from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg


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

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255, verbose_name="Название книги")
    cover = models.ImageField(upload_to='book_covers/', blank=True, null=True, verbose_name="Обложка")
    # Если у книги может быть несколько авторов – используем ManyToManyField
    authors = models.ManyToManyField('Author', related_name="books", verbose_name="Авторы")
    genre = models.CharField(max_length=100, blank=True, verbose_name="Жанр")
    description = models.TextField(blank=True, verbose_name="Описание")
    published_date = models.DateField(blank=True, null=True, verbose_name="Дата издания")
    
    # Фиксированный мировой рейтинг (например, рассчитанный на основе внешних данных)
    world_rating = models.FloatField(blank=True, null=True, verbose_name="Мировой рейтинг")

    def __str__(self):
        return self.title

    @property
    def app_rating(self):
        """
        Вычисляет среднюю оценку, основанную на отзывах пользователей.
        Возвращает None, если отзывов нет.
        """
        reviews = self.reviews.all()  # reviews – related_name из модели Review
        if reviews.exists():
            return reviews.aggregate(average=Avg('rating'))['average']
        return None

    @property
    def all_reviews(self):
        """
        Возвращает QuerySet всех отзывов на книгу.
        """
        return self.reviews.all()

# ----------------------------
# Модель отзыва (от пользователей приложения)
# ----------------------------
class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reviews", verbose_name="Книга")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews", verbose_name="Пользователь")
    # Рейтинг, оставляемый пользователем, от 1 до 5
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Оценка"
    )
    comment = models.TextField(blank=True, null=True, verbose_name="Отзыв")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отзыва")

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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='book_relations')
    # Ссылка на книгу
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='user_relations')
    # Тип списка, в который добавлена книга
    list_type = models.CharField(max_length=20, choices=LIST_TYPE_CHOICES, verbose_name="Тип списка")
    # Время добавления книги в данный список
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    # Дополнительное поле, например, комментарий (опционально)
    comment = models.TextField(blank=True, null=True, verbose_name="Комментарий")

    class Meta:
        # Обеспечивает, что один пользователь не сможет добавить одну и ту же книгу в один и тот же список несколько раз
        unique_together = ('user', 'book', 'list_type')
        verbose_name = "Связь пользователь-книга"
        verbose_name_plural = "Связи пользователь-книга"

    def __str__(self):
        # Метод возвращает строковое представление: имя пользователя, название книги и название списка (через get_list_type_display)
        return f"{self.user.username}: {self.book.title} ({self.get_list_type_display()})"

# ----------------------------
# Модель цитаты
# ----------------------------
class Quote(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="quotes", verbose_name="Книга")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quotes", verbose_name="Пользователь")
    text = models.TextField(verbose_name="Текст цитаты")
    page = models.PositiveIntegerField(blank=True, null=True, verbose_name="Номер страницы")
    chapter = models.CharField(max_length=255, blank=True, null=True, verbose_name="Глава/Раздел")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    is_public = models.BooleanField(default=True, verbose_name="Публичная цитата")
    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="liked_quotes",
        blank=True,
        verbose_name="Лайки"
    )

    class Meta:
        verbose_name = "Цитата"
        verbose_name_plural = "Цитаты"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.book.title} - {self.text[:50]}..."

    @property
    def likes_count(self):
        """
        Возвращает количество лайков цитаты
        """
        return self.likes.count()

    @property
    def short_text(self):
        """
        Возвращает сокращенный текст цитаты для отображения в списках
        """
        return f"{self.text[:100]}..." if len(self.text) > 100 else self.text
