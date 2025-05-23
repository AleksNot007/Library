from django import forms

class OpenLibrarySearchForm(forms.Form):
    title = forms.CharField(
        max_length=255,
        label='Название книги',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите название книги для поиска'
        })
    ) 