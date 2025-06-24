"""
URL configuration for books_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from books import views

from books.api_views import record_book_view, user_recommendations_api, autocomplete_books, book_rate, add_to_bookmarks, add_to_cart
 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),  
    path('signup/', views.signup, name='signup'),  
    path('registration/', views.registration, name='registration'),  
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('autocomplete/', autocomplete_books, name='autocomplete_books'),
    path('profile/', views.profile, name='profile'), 
    path('search/', views.search_books, name='search_books'), 
    path('cart/', views.cart, name='cart'), 
    path('bookmarks/', views.bookmarks, name='bookmarks'), 
    path('books/<int:book_id>/', views.book_detail, name='book_detail'),
    path('books/<int:book_id>/rate/', book_rate, name='book_rate'),
    path('api/cart/add/', add_to_cart, name='add_to_cart'),
    path('api/bookmarks/add/', add_to_bookmarks, name='add_to_bookmarks'),
    path('api/recommendations/user/<int:user_id>/', user_recommendations_api, name='user-recommendations-api'),
    path('api/record-book-view/', record_book_view, name='record-book-view'),
    
]

 
 