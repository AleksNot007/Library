from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

#
# ---------------------------------------------------------------
#
# username – строковое поле, содержащее имя пользователя (уникальное, используется для идентификации при входе).
#
# password – строковое поле для хранения хэшированного пароля.
#
# first_name – строковое поле для хранения имени пользователя.
#
# last_name – строковое поле для хранения фамилии пользователя.
#
# email – строковое поле для адреса электронной почты.
#
# is_staff – логическое поле, указывающее, имеет ли пользователь права доступа к административной панели.
#
# is_active – логическое поле, которое показывает, активен ли аккаунт пользователя.
#
# date_joined – дата и время создания аккаунта.
#
# last_login – дата и время последнего входа пользователя в систему.
#
# ---------------------------------------------------------------
#

class User(AbstractUser):
    # Возраст, поможет в дополнение генерить рекомендации, посмотрим, понадобиться или нет...
    age = models.PositiveIntegerField(blank=True, null=True)
    # Результаты первичного теста об предпочтениях пользователя, тест можно перепройти потом
    preferences = models.JSONField(blank=True, null=True)
    email = models.EmailField(_("email address"), unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.username

    @property
    def has_unread_messages(self):
        """Проверяет, есть ли у пользователя непрочитанные сообщения"""
        return self.moderator_messages.filter(is_read=False).exists()

    @property
    def unread_messages_count(self):
        """Возвращает количество непрочитанных сообщений"""
        return self.moderator_messages.filter(is_read=False).count()

class ModeratorMessage(models.Model):
    MESSAGE_TYPES = (
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
        ('general', 'Общее сообщение'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='moderator_messages')
    book = models.ForeignKey('books.Book', on_delete=models.SET_NULL, null=True, blank=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Сообщение модератора'
        verbose_name_plural = 'Сообщения модератора'

    def __str__(self):
        return f'Сообщение для {self.user.username} ({self.get_message_type_display()})'
