from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from books.models import Book, Author
import json

class Recommendation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="recommendations",
        verbose_name="Пользователь"
    )
    book = models.ForeignKey(
        'books.Book', 
        on_delete=models.CASCADE, 
        related_name="recommendations",
        verbose_name="Книга"
    )
    # Коэффициент рекомендации, например, от 0.0 до 1.0, где 1.0 – максимально высокий
    score = models.FloatField(
        verbose_name="Рейтинг рекомендации",
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Числовое значение, отражающее силу рекомендации (от 0.0 до 1.0)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания рекомендации"
    )

    class Meta:
        unique_together = ('user', 'book')
        verbose_name = "Рекомендация"
        verbose_name_plural = "Рекомендации"

    def __str__(self):
        # Выводим имя пользователя, название книги и рекомендуемую оценку
        return f"{self.user.username} - {self.book.title} (score: {self.score}, {self.percent}%)"

class Language(models.Model):
    code = models.CharField(max_length=2, primary_key=True, verbose_name="Код языка")
    name = models.CharField(max_length=50, verbose_name="Название языка")

    class Meta:
        verbose_name = "Язык"
        verbose_name_plural = "Языки"

    def __str__(self):
        return self.name

class UserSurveyProfile(models.Model):
    READING_GOAL_CHOICES = [
        ('fun', 'Отдых/развлечение'),
        ('inspire', 'Вдохновение/идеи'),
        ('skill', 'Проф-рост'),
        ('study', 'Учёба/исследование'),
    ]

    READING_FREQUENCY_CHOICES = [
        (0.5, '< 1 книг/мес'),
        (1.5, '1–2 книг/мес'),
        (4.0, '3–5 книг/мес'),
        (6.0, '> 5 книг/мес'),
    ]

    MOOD_TAG_CHOICES = [
        ('light', 'Лёгкий/юмористический'),
        ('dark', 'Мрачный/напряжённый'),
        ('meditative', 'Медитативный'),
        ('dynamic', 'Динамичный «page-turner»'),
    ]

    CONTENT_FILTER_CHOICES = [
        ('violence', 'Жестокие сцены'),
        ('animal_cruelty', 'Насилие над животными'),
        ('adult', 'Подробное 18+'),
        ('politics', 'Политика'),
        ('religion', 'Религия'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='survey_profile',
        verbose_name="Пользователь"
    )
    reading_goal = models.CharField(
        max_length=10, 
        choices=READING_GOAL_CHOICES, 
        verbose_name="Цель чтения"
    )
    mood_tags = models.JSONField(
        default=list, 
        verbose_name="Предпочитаемая атмосфера",
        help_text="Список из MOOD_TAG_CHOICES"
    )
    reading_frequency = models.FloatField(
        choices=READING_FREQUENCY_CHOICES, 
        verbose_name="Частота чтения"
    )
    original_languages = models.ManyToManyField(
        Language, 
        verbose_name="Предпочитаемые языки оригинала"
    )
    fav_authors = models.ManyToManyField(
        Author, 
        related_name='favorite_in_survey',
        verbose_name="Любимые авторы",
        blank=True
    )
    fav_books = models.ManyToManyField(
        Book, 
        related_name='favorite_in_survey',
        verbose_name="Любимые книги",
        blank=True
    )
    content_filters = models.JSONField(
        default=list, 
        verbose_name="Контент-фильтры",
        help_text="Список из CONTENT_FILTER_CHOICES"
    )
    other_content_filters = models.TextField(
        blank=True,
        verbose_name="Другие контент-фильтры",
        help_text="Дополнительные фильтры контента, указанные пользователем"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата прохождения опроса"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )

    class Meta:
        verbose_name = "Профиль читательских предпочтений"
        verbose_name_plural = "Профили читательских предпочтений"

    def __str__(self):
        return f"Профиль {self.user.username}"

    def set_mood_tags(self, tags):
        """Установить теги атмосферы из списка"""
        self.mood_tags = json.dumps([tag for tag in tags if tag in dict(self.MOOD_TAG_CHOICES)])

    def get_mood_tags(self):
        """Получить список тегов атмосферы"""
        return json.loads(self.mood_tags) if self.mood_tags else []

    def set_content_filters(self, filters):
        """Установить фильтры контента из списка"""
        self.content_filters = json.dumps([f for f in filters if f in dict(self.CONTENT_FILTER_CHOICES)])

    def get_content_filters(self):
        """Получить список фильтров контента"""
        return json.loads(self.content_filters) if self.content_filters else []

class UserGenrePreference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='survey_genre_preferences',
        verbose_name="Пользователь"
    )
    genre = models.CharField(
        max_length=50,
        choices=Book.GENRE_CHOICES,
        verbose_name="Жанр"
    )
    weight = models.IntegerField(
        default=0,
        verbose_name="Вес предпочтения",
        help_text="1 для предпочтительных, -1 для нежелательных жанров"
    )

    class Meta:
        unique_together = ('user', 'genre')
        verbose_name = "Жанровое предпочтение"
        verbose_name_plural = "Жанровые предпочтения"

    def __str__(self):
        return f"{self.user.username} - {self.get_genre_display()} ({self.weight})"