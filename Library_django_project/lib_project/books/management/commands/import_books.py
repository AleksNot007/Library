import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from books.models import Book, Author

GENRE_MAPPING = {
    'Фэнтези': 'fantasy',
    'Фантастика': 'sci_fi',
    'Триллеры': 'thriller_horror',
    'Ужасы': 'thriller_horror',
    'Детектив': 'detective',
    'Романтика': 'romance',
    'Классика': 'classic',
    'Проза': 'prose',
    'История': 'history',
    'Биография': 'biography',
    'Психология': 'psychology',
    'Философия': 'non_fiction',
    'Научная литература': 'non_fiction',
    'Научная фантастика': 'sci_fi',
    'Приключения': 'other',
    'Поэзия': 'other',
    'Драма': 'drama',
    'Комедия': 'other',
    'Боевик': 'other',
    'Мистика': 'thriller_horror',
    'Сказка': 'children',
    'Роман': 'prose'
}

class Command(BaseCommand):
    help = 'Импорт книг из CSV файла'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV файлу')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        # Получаем или создаем пользователя-администратора
        User = get_user_model()
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={'is_staff': True, 'is_superuser': True}
        )
        
        # Открываем файл в режиме чтения байтов для определения BOM
        with open(csv_file_path, 'rb') as file:
            raw_data = file.read()
            if raw_data.startswith(b'\xef\xbb\xbf'):  # UTF-8 BOM
                encoding = 'utf-8-sig'
            else:
                encoding = 'utf-8'
        
        # Теперь открываем файл с правильной кодировкой
        with open(csv_file_path, 'r', encoding=encoding) as file:
            # Читаем первую строку для определения заголовков
            dialect = csv.Sniffer().sniff(file.read(1024))
            file.seek(0)
            
            csv_reader = csv.DictReader(file, dialect=dialect)
            
            for row in csv_reader:
                try:
                    # Создаем или получаем автора
                    author_name = row['Автор'].strip()
                    author, created = Author.objects.get_or_create(
                        name=author_name,
                        defaults={
                            'century': int(row['Дата издания'].strip()[:4]) // 100 + 1,  # Определяем век по году
                            'country': 'Неизвестно'  # Так как в CSV нет этой информации
                        }
                    )
                    
                    # Определяем жанр
                    csv_genre = row['Жанр'].strip()
                    genre_code = GENRE_MAPPING.get(csv_genre, 'other')
                    
                    # Создаем книгу
                    book = Book.objects.create(
                        title=row['Название'].strip(),
                        genre=genre_code,
                        description=row['Описание'].strip(),
                        published_date=datetime.strptime(row['Дата издания'].strip(), '%Y').date(),
                        world_rating=float(row['Мировой рейтинг'].strip()),
                        is_approved=True,  # Автоматически одобряем импортированные книги
                        submitted_by=admin_user
                    )
                    
                    # Добавляем автора к книге
                    book.authors.add(author)
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Успешно импортирована книга "{row["Название"]}"')
                    )
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Ошибка при импорте книги: {str(e)}')
                    ) 