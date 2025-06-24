from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import BookRating, UserSubscription, BookView, UserPreferences


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
    class Meta:
        model = UserPreferences
        fields = []   