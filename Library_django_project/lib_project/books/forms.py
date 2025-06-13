from django import forms
from .models import Book, Review, Quote, UserBookRelation

class OpenLibrarySearchForm(forms.Form):
    title = forms.CharField(
        max_length=255,
        label='Название книги',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите название книги для поиска'
        })
    )

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            'title', 
            'authors', 
            'description', 
            'cover', 
            'published_date',
            'genre', 
            'pages', 
            'isbn',
            'online_sources',
            'world_rating'
        ]
        widgets = {
            'published_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 5}),
            'online_sources': forms.Textarea(
                attrs={
                    'rows': 3, 
                    'placeholder': 'Введите источники в формате:\nНазвание сайта: URL\nНазвание сайта 2: URL2'
                }
            ),
            'pages': forms.NumberInput(
                attrs={
                    'min': 1,
                    'placeholder': 'Введите количество страниц'
                }
            )
        }

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment', 'spoiler']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 5}),
            'spoiler': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = ['text', 'page', 'is_public']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4}),
            'page': forms.NumberInput(attrs={'min': 1}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class UserBookRelationForm(forms.ModelForm):
    class Meta:
        model = UserBookRelation
        fields = ['progress_pages', 'notes']
        widgets = {
            'progress_pages': forms.NumberInput(attrs={'min': 0}),
            'notes': forms.Textarea(attrs={'rows': 5})
        } 