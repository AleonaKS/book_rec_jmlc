from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import BookRating, UserSubscription, BookView, UserPreferences, Author, Tag, Genre
from .models import UserPreferences, FavoriteAuthors, FavoriteGenres, FavoriteTags, DislikedGenres, DislikedTags

class SignUpForm(UserCreationForm): 
    class Meta:
        model = User
        fields = ('username', 'password1', 'password2')

class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Имя пользователя')
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)


class BookRatingForm(forms.ModelForm):
    class Meta:
        model = BookRating
        fields = ['book', 'rating']

class UserSubscriptionForm(forms.ModelForm):
    class Meta:
        model = UserSubscription
        fields = ['content_type', 'author', 'cycle']

class BookViewForm(forms.ModelForm):
    class Meta:
        model = BookView
        fields = ['book', 'duration_seconds', 'scroll_depth']




class UserPreferencesForm(forms.ModelForm):
    favorite_authors = forms.ModelMultipleChoiceField(
        queryset=Author.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    favorite_genres = forms.ModelMultipleChoiceField(
        queryset=Genre.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    favorite_tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    disliked_genres = forms.ModelMultipleChoiceField(
        queryset=Genre.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    disliked_tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = UserPreferences
        fields = []

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        
        # Инициализация текущих предпочтений с оценками
        self._init_preferences_field('favorite_authors', FavoriteAuthors, 'author')
        self._init_preferences_field('favorite_genres', FavoriteGenres, 'genre')
        self._init_preferences_field('favorite_tags', FavoriteTags, 'tag')
        self._init_preferences_field('disliked_genres', DislikedGenres, 'genre')
        self._init_preferences_field('disliked_tags', DislikedTags, 'tag')

    def _init_preferences_field(self, field_name, through_model, relation_field):
        # Инициализирует поле формы с учетом текущих оценок
        if self.instance.pk: 
            through_objects = through_model.objects.filter(
                userprofile=self.instance
            ).select_related(relation_field)
             
            if not hasattr(self, '_preferences_scores'):
                self._preferences_scores = {}
            
            for obj in through_objects:
                item = getattr(obj, relation_field)
                self._preferences_scores[f'{field_name}_{item.id}'] = obj.score
             
            self.fields[field_name].initial = [getattr(obj, relation_field) for obj in through_objects]

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save() 

            self._save_preferences(
                instance=instance,
                field_name='favorite_authors',
                through_model=FavoriteAuthors,
                relation_field='author',
                score_prefix='favoriteauthors_score'
            )
            
            self._save_preferences(
                instance=instance,
                field_name='favorite_genres',
                through_model=FavoriteGenres,
                relation_field='genre',
                score_prefix='favoritegenres_score'
            )
            
            self._save_preferences(
                instance=instance,
                field_name='favorite_tags',
                through_model=FavoriteTags,
                relation_field='tag',
                score_prefix='favoritetags_score'
            )
            
            self._save_preferences(
                instance=instance,
                field_name='disliked_genres',
                through_model=DislikedGenres,
                relation_field='genre',
                score_prefix='dislikedgenres_score'
            )
            
            self._save_preferences(
                instance=instance,
                field_name='disliked_tags',
                through_model=DislikedTags,
                relation_field='tag',
                score_prefix='dislikedtags_score'
            )
        
        return instance

    def _save_preferences(self, instance, field_name, through_model, relation_field, score_prefix):
        try:
            current_items = {
                getattr(obj, relation_field): obj 
                for obj in through_model.objects.filter(userprofile=instance)
            }
            
            new_items = set(self.cleaned_data[field_name])
            
            # Удаляем элементы, которые были сняты
            for item in set(current_items.keys()) - new_items:
                current_items[item].delete()
            
            # Добавляем/обновляем новые элементы
            for item in new_items:
                # Получаем оценку из POST-данных или из сохраненных в __init__
                score = self.data.get(f'{score_prefix}_{item.id}') or \
                    getattr(self, '_preferences_scores', {}).get(f'{field_name}_{item.id}', 0)
                
                try:
                    score = float(score)
                    score = max(0, min(10, score))   
                except (ValueError, TypeError):
                    score = 0
                
                # Обновляем или создаем запись
                if item in current_items:
                    if current_items[item].score != score:
                        current_items[item].score = score
                        current_items[item].save()
                else:
                    through_model.objects.create(
                        userprofile=instance,
                        **{relation_field: item},
                        score=score
                    )
        except ValidationError as e:
            self.add_error(field_name, e)

    
    def clean(self):
        cleaned_data = super().clean()
        
        # Проверка на пересечение любимых и нелюбимых жанров
        favorite_genres = set(cleaned_data.get('favorite_genres', []))
        disliked_genres = set(cleaned_data.get('disliked_genres', []))
        conflicting_genres = favorite_genres & disliked_genres
        
        if conflicting_genres:
            genre_names = ", ".join(str(g) for g in conflicting_genres)
            self.add_error('favorite_genres', 
                         f"Эти жанры не могут быть одновременно любимыми и нелюбимыми: {genre_names}")
            self.add_error('disliked_genres', 
                         f"Эти жанры не могут быть одновременно любимыми и нелюбимыми: {genre_names}")
        
        # Проверка на пересечение любимых и нелюбимых тегов
        favorite_tags = set(cleaned_data.get('favorite_tags', []))
        disliked_tags = set(cleaned_data.get('disliked_tags', []))
        conflicting_tags = favorite_tags & disliked_tags
        
        if conflicting_tags:
            tag_names = ", ".join(str(t) for t in conflicting_tags)
            self.add_error('favorite_tags', 
                         f"Эти теги не могут быть одновременно любимыми и нелюбимыми: {tag_names}")
            self.add_error('disliked_tags', 
                         f"Эти теги не могут быть одновременно любимыми и нелюбимыми: {tag_names}")
        
        return cleaned_data