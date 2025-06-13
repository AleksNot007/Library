from django.urls import path
from . import views

app_name = 'recommendations'

urlpatterns = [
    # Шаги опроса
    path('survey/step1/', views.survey_step1, name='survey_step1'),  # Предпочитаемые жанры
    path('survey/step2/', views.survey_step2, name='survey_step2'),  # Нежелательные жанры
    path('survey/step3/', views.survey_step3, name='survey_step3'),  # Цель чтения
    path('survey/step4/', views.survey_step4, name='survey_step4'),  # Частота чтения
    path('survey/step5/', views.survey_step5, name='survey_step5'),  # Любимые авторы
    path('survey/step6/', views.survey_step6, name='survey_step6'),  # Любимые книги
    
    # API для получения данных
    path('api/authors/', views.get_authors, name='get_authors'),
    path('api/books-by-genres/', views.get_books_by_genres, name='get_books_by_genres'),
    path('api/update-recommendations/', views.update_recommendations_view, name='update_recommendations'),
    
    # Сохранение результатов каждого шага
    path('survey/save-step1/', views.save_step1, name='save_step1'),
    path('survey/save-step2/', views.save_step2, name='save_step2'),
    path('survey/save-step3/', views.save_step3, name='save_step3'),
    path('survey/save-step4/', views.save_step4, name='save_step4'),
    path('survey/save-step5/', views.save_step5, name='save_step5'),
    path('survey/save-step6/', views.save_step6, name='save_step6'),
    
    # Завершение опроса
    path('survey/complete/', views.survey_complete, name='survey_complete'),
    
    # Редирект со старого URL на первый шаг
    path('survey/', views.survey_redirect, name='survey'),
] 