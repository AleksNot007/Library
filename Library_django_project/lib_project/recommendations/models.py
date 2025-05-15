from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

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