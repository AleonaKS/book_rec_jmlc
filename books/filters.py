import django_filters
from django import forms
from .models import Book, Tag, Genre, Publisher

class BookFilter(django_filters.FilterSet):
    genre = django_filters.ModelChoiceFilter(
        field_name='genre',
        queryset=Genre.objects.all(),
        empty_label='Все жанры',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    publisher = django_filters.ModelChoiceFilter(
        field_name='publisher',
        queryset=Publisher.objects.all(),
        empty_label='Все издательства',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name='tags',
        queryset=Tag.objects.all(),
        conjoined=False,
        widget=forms.CheckboxSelectMultiple,
    )  
    new = django_filters.BooleanFilter(field_name='new', widget=forms.CheckboxInput)
    soon = django_filters.BooleanFilter(field_name='soon', widget=forms.CheckboxInput)
    age_restriction = django_filters.ChoiceFilter(
        choices=(
            ('', 'Без ограничений'),
            ('0+', '0+'),
            ('6+', '6+'),
            ('12+', '12+'),
            ('16+', '16+'),
            ('18+', '18+'),
        ),
        field_name='age_restriction',
        lookup_expr='exact'
    )

    class Meta:
        model = Book
        fields = ['genre', 'author', 'cycle', 'series', 'publisher', 'tags', 'new', 'soon', 'age_restriction', 'cover_type']
 
 