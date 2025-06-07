from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.conf import settings
from .models import User
import re
import dns.resolver
from email_validator import validate_email, EmailNotValidError

class UserRegistrationForm(UserCreationForm):
    error_messages = {
        'password_mismatch': 'Пароли не совпадают.',
        'password_too_short': 'Пароль слишком короткий. Он должен содержать как минимум 8 символов.',
        'password_too_common': 'Этот пароль слишком простой.',
        'password_entirely_numeric': 'Пароль не может состоять только из цифр.',
        'password_no_letter': 'Пароль должен содержать хотя бы одну английскую букву.',
        'password_no_number': 'Пароль должен содержать хотя бы одну цифру.',
        'password_invalid_chars': 'Пароль может содержать только английские буквы, цифры и символы _ . -',
        'email_invalid_format': 'Введите корректный email адрес.',
        'email_domain_not_exists': 'Домен указанного email адреса не существует.',
        'email_not_valid': 'Указанный email адрес недействителен.',
    }

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите email'
        })
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите имя пользователя (только английские буквы и цифры)'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль (английские буквы, цифры и символы _ . -)',
            'data-min-length': '8',
            'oninput': 'checkPassword(this)'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Подтвердите пароль',
            'oninput': 'checkPasswordMatch()'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            raise forms.ValidationError(
                'Имя пользователя может содержать только английские буквы, цифры и символы _ . -'
            )
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Проверка на существующий email
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError('Этот email уже используется')
            
            try:
                # Проверка формата email и нормализация
                valid = validate_email(email)
                email = valid.email

                # Получаем домен из email
                domain = email.split('@')[1]
                
                # Проверяем существование MX-записи для домена
                try:
                    dns.resolver.resolve(domain, 'MX')
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                    raise forms.ValidationError(self.error_messages['email_domain_not_exists'])
                except Exception:
                    # В случае других ошибок DNS (например, timeout) пропускаем эту проверку
                    pass

            except EmailNotValidError:
                raise forms.ValidationError(self.error_messages['email_not_valid'])
            
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        
        # Проверяем, что пароль содержит только разрешенные символы
        if not re.match(r'^[a-zA-Z0-9_.-]+$', password):
            raise forms.ValidationError(self.error_messages['password_invalid_chars'])
        
        try:
            validate_password(password)
        except ValidationError as e:
            errors = []
            for error in e.error_list:
                if 'This password is too short' in str(error):
                    errors.append(forms.ValidationError(self.error_messages['password_too_short']))
                elif 'This password is too common' in str(error):
                    errors.append(forms.ValidationError(self.error_messages['password_too_common']))
                elif 'This password is entirely numeric' in str(error):
                    errors.append(forms.ValidationError(self.error_messages['password_entirely_numeric']))
                else:
                    errors.append(error)
            if errors:
                raise forms.ValidationError(errors)

        # Проверяем наличие английской буквы
        if not any(char.isalpha() and char.isascii() for char in password):
            raise forms.ValidationError(self.error_messages['password_no_letter'])
        
        # Проверяем наличие цифры
        if not any(char.isdigit() for char in password):
            raise forms.ValidationError(self.error_messages['password_no_number'])
        
        return password

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(self.error_messages['password_mismatch'])
        return password2

    def clean(self):
        cleaned_data = super().clean()
        if self._errors:  # Если уже есть ошибки, не продолжаем
            return cleaned_data
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class CustomAuthenticationForm(AuthenticationForm):
    """
    Форма аутентификации с поддержкой входа по email или username
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите email или имя пользователя'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль'
        })
    )

    error_messages = {
        'invalid_login': 'Пожалуйста, введите правильные email/имя пользователя и пароль.',
        'inactive': 'Этот аккаунт неактивен.',
    } 