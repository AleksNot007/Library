from django.db import models
from django.contrib.auth.models import AbstractUser

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

    def __str__(self):
        return self.username
