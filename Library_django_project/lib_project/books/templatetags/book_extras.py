from django import template

register = template.Library()

@register.filter(name='get_language_name')
def get_language_name(code):
    """Возвращает название языка по его коду"""
    languages = {
        'rus': 'Русский',
        'eng': 'Английский',
        'fre': 'Французский',
        'ger': 'Немецкий',
        'spa': 'Испанский',
        'ita': 'Итальянский',
        'chi': 'Китайский',
        'jpn': 'Японский',
        'kor': 'Корейский',
        'ara': 'Арабский',
        'por': 'Португальский',
        'hin': 'Хинди',
        'ben': 'Бенгальский',
        'pol': 'Польский',
        'ukr': 'Украинский',
        'vie': 'Вьетнамский',
        'tur': 'Турецкий',
        'per': 'Персидский',
        'heb': 'Иврит',
        'tha': 'Тайский',
    }
    return languages.get(code, code) 