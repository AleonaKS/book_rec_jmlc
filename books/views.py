import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User 
from django.contrib.auth.decorators import login_required 
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_GET, require_POST
from django.middleware.csrf import get_token
from django.db import transaction
from django.db.models import OuterRef, Subquery, Exists,  Value, BooleanField
from django.core.paginator import Paginator
from haystack.query import SearchQuerySet
from .filters import BookFilter 
from .forms import SignUpForm, UserPreferencesForm #, LoginForm, BookRatingForm
from .models import Book, Genre, Publisher, Tag, Author, Series, Cycle, Review, BookView, BookRating, UserBookStatus, UserPreferences
from .models import UserPreferences, UserSubscription, FavoriteAuthors, FavoriteGenres, FavoriteTags, DislikedGenres, DislikedTags
from books.recommendations.base_recommendations import recommendations_split, recommendations_for_anonymous, recommendations_for_user_without_preferences
from books.recommendations.hybrid import hybrid_recommendations_for_user, hybrid_recommendations_for_book

import random
logger = logging.getLogger(__name__)
 


def home_view(request):
    popular_books, new_books, soon_books = None, None, None
    recommended_books = []

    if request.user.is_authenticated:
        user = request.user
        user_views = BookView.objects.filter(user=user).order_by('-viewed_at')

        # Получаем все гибридные рекомендации (например, 50 штук)
        recommended_books_all = hybrid_recommendations_for_user(user, top_n=50)

        try:
            prefs = user.userpreferences
            favorite_genres = prefs.favorite_genres.all().values_list('id', flat=True)
            favorite_tags = prefs.favorite_tags.all().values_list('id', flat=True)
            popular_cold, new_cold, soon_cold = recommendations_split(user, list(favorite_genres), list(favorite_tags), top_n=50)
        except UserPreferences.DoesNotExist:
            popular_cold, new_cold, soon_cold = recommendations_for_user_without_preferences(user, top_n=50)

        used_ids = set()
 
        new_books = [b for b in recommended_books_all if b.new]
        used_ids.update(b.id for b in new_books)
 
        new_candidates = [b for b in new_cold if b.id not in used_ids]
        new_books.extend(new_candidates)
        used_ids.update(b.id for b in new_candidates)
 
        if len(new_books) < 30:
            needed = 30 - len(new_books)
            extra_new = Book.objects.filter(new=True).exclude(id__in=used_ids).order_by('?')[:needed]
            new_books.extend(extra_new)
            used_ids.update(b.id for b in extra_new)

        new_books = new_books[:30]
 
        soon_books = [b for b in recommended_books_all if b.soon and b.id not in used_ids]
        used_ids.update(b.id for b in soon_books)
 
        soon_candidates = [b for b in soon_cold if b.id not in used_ids]
        soon_books.extend(soon_candidates)
        used_ids.update(b.id for b in soon_candidates)
 
        if len(soon_books) < 30:
            needed = 30 - len(soon_books)
            extra_soon = Book.objects.filter(soon=True).exclude(id__in=used_ids).order_by('?')[:needed]
            soon_books.extend(extra_soon)
            used_ids.update(b.id for b in extra_soon)

        soon_books = soon_books[:30]
 
        popular_candidates = [b for b in popular_cold if not b.new and not b.soon and b.id not in used_ids]
        popular_books = popular_candidates[:30]
        used_ids.update(b.id for b in popular_books)

        # Если мало, дополняем рандомными книгами без new и soon
        if len(popular_books) < 30:
            needed = 30 - len(popular_books)
            extra_popular = Book.objects.filter(new=False, soon=False).exclude(id__in=used_ids).order_by('?')[:needed]
            popular_books.extend(extra_popular)
            used_ids.update(b.id for b in extra_popular)
 
        recommended_candidates = [b for b in recommended_books_all if not b.new and not b.soon and b.id not in used_ids]
        recommended_books = recommended_candidates[:30]
        used_ids.update(b.id for b in recommended_books)

        # # Если мало, дополняем рандомными книгами без new и soon
        # if len(recommended_books) < 30:
        #     needed = 30 - len(recommended_books)
        #     extra_rec = Book.objects.filter(new=False, soon=False).exclude(id__in=used_ids).order_by('?')[:needed]
        #     recommended_books.extend(extra_rec)
        #     used_ids.update(b.id for b in extra_rec)

    else:
        # Анонимный пользователь
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key

        # popular_books, new_books, soon_books = recommendations_for_anonymous(session_key)
        # # recommended_books для анонима — популярные без new и soon, чтобы не пересекались
        # recommended_books = [b for b in popular_books if not b.new and not b.soon][:30]
        # recommended_ids = {b.id for b in recommended_books}
        # popular_books = [b for b in popular_books if b.id not in recommended_ids]
        popular_books, new_books, soon_books, recommended_books = recommendations_for_anonymous(session_key)
        user_views = BookView.objects.filter(user__isnull=True, session_key=session_key).order_by('-viewed_at')

    # Последние просмотренные книги (до 20)
    last_20_book_ids = list(user_views.values_list('book_id', flat=True).distinct()[:20])
    books = list(Book.objects.filter(id__in=last_20_book_ids))
    last_books = sorted(books, key=lambda b: last_20_book_ids.index(b.id))

    # Сохраняем id в сессии
    request.session['recommended_book_ids'] = [book.id for book in recommended_books] if recommended_books else []
    request.session['popular_book_ids'] = [book.id for book in popular_books] if popular_books else []
    request.session['new_book_ids'] = [book.id for book in new_books] if new_books else []
    request.session['soon_book_ids'] = [book.id for book in soon_books] if soon_books else []

    context = {
        'recommended_books': recommended_books,
        'popular_books': popular_books,
        'new_books': new_books,
        'soon_books': soon_books,
        'last_books': last_books
    }
    return render(request, 'home.html', context)







def switch_keyboard_layout(text):
    layout_en = 'qwertyuiop[]asdfghjkl;\'zxcvbnm,./`QWERTYUIOP{}ASDFGHJKL:"ZXCVBNM<>?~'
    layout_ru = 'йцукенгшщзхъфывапролджэячсмитьбю.ёЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,Ё'
    assert len(layout_en) == len(layout_ru), "Раскладки должны быть одинаковой длины"
    trans_table = str.maketrans(layout_en + layout_ru, layout_ru + layout_en)
    return text.translate(trans_table)


@require_GET
def search_books(request):
    query = request.GET.get('q', '').strip()
    genre = request.GET.get('genre', '').strip()
    author = request.GET.get('author', '').strip()
    cycle = request.GET.get('cycle', '').strip()
    publisher = request.GET.get('publisher', '').strip()
    series = request.GET.get('series', '').strip()
    tag = request.GET.get('tag', '').strip()
    sort = request.GET.get('sort_by', '')

    qs = Book.objects.all()

    # Фильтрация по параметрам
    if genre:
        qs = qs.filter(genre__name__iexact=genre)
    if author:
        qs = qs.filter(author__name__iexact=author)
    if cycle:
        qs = qs.filter(cycle__name__iexact=cycle)
    if publisher:
        qs = qs.filter(publisher__name__iexact=publisher)
    if series:
        qs = qs.filter(series__name__iexact=series)
    if tag:
        qs = qs.filter(tags__name__iexact=tag)

    # Поиск по тексту, если есть
    if query:
        alt_query = switch_keyboard_layout(query) if query else ''
        sqs_title_main = SearchQuerySet().autocomplete(content_auto=query)
        sqs_title_alt = SearchQuerySet().autocomplete(content_auto=alt_query) if alt_query else SearchQuerySet().none()
        sqs_author_main = SearchQuerySet().autocomplete(author_auto=query)
        sqs_author_alt = SearchQuerySet().autocomplete(author_auto=alt_query) if alt_query else SearchQuerySet().none()

        sqs = (sqs_title_main | sqs_title_alt | sqs_author_main | sqs_author_alt).load_all()
        books = [res.object for res in sqs if res.object is not None][:100]
        book_ids = [book.id for book in books]
        qs = qs.filter(id__in=book_ids)

    # Сортировка
    if sort == 'popularity':
        qs = qs.order_by('-popularity_score')
    elif sort == 'newness':
        qs = qs.order_by('-year_of_publishing')

    book_filter = BookFilter(request.GET, queryset=qs)
    filtered_books = list(book_filter.qs)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        results = [{'id': b.id, 'title': b.title, 'author': ', '.join(a.name for a in b.author.all())} for b in filtered_books[:20]]
        return JsonResponse(results, safe=False)

    context = {
        'books': filtered_books,
        'filter': book_filter,
        'query': query,
        'sort': sort,
    }
    return render(request, 'search.html', context)



# def home_view(request):
#     popular_books, new_books, soon_books = None, None, None
#     if request.user.is_authenticated:
#         user_views = BookView.objects.filter(user=request.user).order_by('-viewed_at')
#         user = request.user
#         recommended_books = hybrid_recommendations_for_user(user, top_n=30)
#         try:
#             prefs = user.userpreferences
#             favorite_genres = prefs.favorite_genres.all().values_list('id', flat=True)
#             favorite_tags = prefs.favorite_tags.all().values_list('id', flat=True)
#             # recommended_books = hybrid_recommendations_for_user(user, top_n=30)
#             popular_books, new_books, soon_books = recommendations_split(user, list(favorite_genres), list(favorite_tags), top_n=30)
#         except UserPreferences.DoesNotExist:
#             popular_books, new_books, soon_books = recommendations_for_user_without_preferences(user, top_n=30)
#     else:
#         session_key = request.session.session_key
#         if not session_key:
#             request.session.create()
#             session_key = request.session.session_key
#         user_views = BookView.objects.filter(user__isnull=True, session_key=session_key).order_by('-viewed_at')
#         popular_books, new_books, soon_books = recommendations_for_anonymous(session_key)
#         recommended_books = popular_books

#     last_20_book_ids = list(user_views.values_list('book_id', flat=True).distinct()[:20])
#     books = list(Book.objects.filter(id__in=last_20_book_ids))
#     last_books = sorted(books, key=lambda b: last_20_book_ids.index(b.id))

#     request.session['recommended_book_ids'] = [book.id for book in recommended_books] if recommended_books else []
#     request.session['popular_book_ids'] = [book.id for book in popular_books] if popular_books else []
#     request.session['new_book_ids'] = [book.id for book in new_books] if new_books else []
#     request.session['soon_book_ids'] = [book.id for book in soon_books] if soon_books else []

#     context = {
#         'recommended_books': recommended_books,
#         'popular_books': popular_books,
#         'new_books': new_books,
#         'soon_books': soon_books,
#         'last_books': last_books
#     }
#     return render(request, 'home.html', context)




def book_detail(request, book_id):
    user = request.user
    book = get_object_or_404(Book, id=book_id)
    in_cart = False
    in_bookmarks = False
    if user.is_authenticated:
        in_cart = UserBookStatus.objects.filter(user=user, book=book, status=UserBookStatus.STATUS_CART).exists()
        in_bookmarks = UserBookStatus.objects.filter(user=user, book=book, status=UserBookStatus.STATUS_WISHLIST).exists()
    similar_books = hybrid_recommendations_for_book(book, top_n=10) 
    context = {
        'book': book,
        'in_cart': in_cart,
        'in_bookmarks': in_bookmarks,
        'csrf_token': get_token(request), 
        'similar_books': similar_books
    }
    return render(request, 'book_detail.html', context)





#  ===================== 
def catalog(request):
    f = BookFilter(request.GET, queryset=Book.objects.all())
    qs = f.qs

    sort = request.GET.get('sort', 'popular')
    if sort == 'price_asc':
        qs = qs.order_by('price')
    elif sort == 'price_desc':
        qs = qs.order_by('-price')
    elif sort == 'year_asc':
        qs = qs.order_by('year_of_publishing')
    elif sort == 'year_desc':
        qs = qs.order_by('-year_of_publishing')
    elif sort == 'rating_desc':
        qs = qs.order_by('-rating_chitai_gorod')
    else:
        qs = qs.order_by('-votes_chitai_gorod', '-rating_chitai_gorod')

    # Аннотации для пользователя
    if request.user.is_authenticated:
        user_book_status_qs = UserBookStatus.objects.filter(user=request.user, book=OuterRef('pk'))
        qs = qs.annotate(
            in_cart=Exists(user_book_status_qs.filter(status=UserBookStatus.STATUS_CART)),
            in_bookmarks=Exists(user_book_status_qs.filter(status=UserBookStatus.STATUS_WISHLIST)),
        )
    else:
        qs = qs.annotate(
            in_cart=Value(False, output_field=BooleanField()),
            in_bookmarks=Value(False, output_field=BooleanField()),
        )

    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    authors = Author.objects.all().order_by('name')
    series = Series.objects.all().order_by('name')
    cycles = Cycle.objects.all().order_by('name')

    context = {
        'title': 'Каталог книг',
        'authors': authors,
        'series': series,
        'cycles': cycles,
        'filter': f,
        'books': page_obj,
        'genres': Genre.objects.all(),
        'publishers': Publisher.objects.all(),
        'tags': Tag.objects.all(),
        'filter_params': request.GET,
        'sort': sort,
        'page_obj': page_obj,
    }
    return render(request, 'catalog.html', context)









@login_required
def books_by_user(request, user_id):
    if request.user.id != user_id:
        return HttpResponseForbidden()
    user_ratings_subquery = BookRating.objects.filter(
        user_id=user_id,
        book=OuterRef('pk')
    ).values('rating')[:1]
    books = Book.objects.annotate(
        user_rating=Subquery(user_ratings_subquery)
    ).filter(user_rating__isnull=False)
    return render(request, 'books_by_user.html', {'books': books})

 

CATEGORY_NAMES = {
    'recommended': 'Рекомендованные книги',
    'popular': 'Популярные книги',
    'new': 'Новые книги',
    'soon': 'Скоро в продаже',
    'marked': 'Ваши оценки',
}


def books_by_category(request, category_slug=None):
    books = Book.objects.all()
    category_name = 'Книги'
    current_cycle_obj = None
    current_author_obj = None 
    user_cycle_subscriptions = set()
    user_author_subscriptions = set()

    if category_slug in ['recommended', 'popular', 'new', 'soon']:
        session_key_map = {
            'recommended': 'recommended_book_ids',
            'popular': 'popular_book_ids',
            'new': 'new_book_ids',
            'soon': 'soon_book_ids',
        }
        book_ids = request.session.get(session_key_map.get(category_slug), [])
        if not book_ids:
            books = Book.objects.none()
        else:
            books_qs = Book.objects.filter(id__in=book_ids)

            if request.user.is_authenticated:
                user_book_status_qs = UserBookStatus.objects.filter(user=request.user, book=OuterRef('pk'))
                books_qs = books_qs.annotate(
                    in_cart=Exists(user_book_status_qs.filter(status=UserBookStatus.STATUS_CART)),
                    in_bookmarks=Exists(user_book_status_qs.filter(status=UserBookStatus.STATUS_WISHLIST)),
                )
            else:
                books_qs = books_qs.annotate(
                    in_cart=Value(False, output_field=BooleanField()),
                    in_bookmarks=Value(False, output_field=BooleanField()),
                )

            books = list(books_qs)
            # Сортируем книги по порядку из book_ids
            books.sort(key=lambda b: book_ids.index(b.id))

        category_name = CATEGORY_NAMES.get(category_slug, 'Книги')

    else:
        author_name = request.GET.get('author')
        series_name = request.GET.get('series')
        cycle_name = request.GET.get('cycle')

        if author_name:
            books = books.filter(author__name=author_name)
            category_name = f'Автор: {author_name}'
        elif series_name:
            books = books.filter(series__name=series_name)
            category_name = f'Серия: {series_name}'
        elif cycle_name:
            books = books.filter(cycle__name=cycle_name)
            category_name = f'Цикл: {cycle_name}'

        if request.user.is_authenticated:
            user_book_status_qs = UserBookStatus.objects.filter(user=request.user, book=OuterRef('pk'))
            books = books.annotate(
                in_cart=Exists(user_book_status_qs.filter(status=UserBookStatus.STATUS_CART)),
                in_bookmarks=Exists(user_book_status_qs.filter(status=UserBookStatus.STATUS_WISHLIST)),
            )
        else:
            books = books.annotate(
                in_cart=Value(False, output_field=BooleanField()),
                in_bookmarks=Value(False, output_field=BooleanField()),
            )

 
        if cycle_name:
            current_cycle_obj = get_object_or_404(Cycle, name=cycle_name)
        if author_name:
            current_author_obj = get_object_or_404(Author, name=author_name) 
        user = request.user
        if user.is_authenticated:
            user_cycle_subscriptions = set(user.usersubscription_set.filter(content_type='CYCLE').values_list('cycle_id', flat=True))
            user_author_subscriptions = set(user.usersubscription_set.filter(content_type='AUTHOR').values_list('author_id', flat=True))
    context = {
        'books': books,
        'category_name': category_name,
        'csrf_token': get_token(request),

        'cycle_obj': current_cycle_obj,  
        'author_obj': current_author_obj, 
        'user_cycle_subscriptions': user_cycle_subscriptions,
        'user_author_subscriptions': user_author_subscriptions,
    }
    return render(request, 'books_by_category.html', context)


# ==========================
 

@login_required
def profile(request):
    user = request.user

    # Получаем подписки пользователя
    subscriptions = UserSubscription.objects.filter(user=user).select_related('author', 'cycle')
    author_subscriptions = [s.author for s in subscriptions if s.content_type == 'AUTHOR' and s.author]
    cycle_subscriptions = [s.cycle for s in subscriptions if s.content_type == 'CYCLE' and s.cycle]

    # Получаем или создаём настройки пользователя (UserPreferences)
    preferences, _ = UserPreferences.objects.get_or_create(user=user)

    # Получаем оценки пользователя для книг (пример)
    user_ratings_subquery = BookRating.objects.filter(
        user=user,
        book=OuterRef('pk')
    ).values('rating')[:1]

    books = Book.objects.annotate(
        user_rating=Subquery(user_ratings_subquery)
    ).filter(user_rating__isnull=False)

    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=preferences, user=user)
        if form.is_valid():
            preferences = form.save()  # Сохраняем настройки и оценки через форму
            messages.success(request, 'Настройки сохранены')
            return redirect('profile')
    else:
        form = UserPreferencesForm(instance=preferences, user=user)

    # Получаем объекты с фильтрацией по userprofile=preferences
    favorite_authors = FavoriteAuthors.objects.filter(userprofile=preferences).select_related('author') 
    favorite_genres = FavoriteGenres.objects.filter(userprofile=preferences).select_related('genre')
    disliked_genres = DislikedGenres.objects.filter(userprofile=preferences).select_related('genre')
    favorite_tags = FavoriteTags.objects.filter(userprofile=preferences).select_related('tag')
    disliked_tags = DislikedTags.objects.filter(userprofile=preferences).select_related('tag')

    context = {
        'author_subscriptions': author_subscriptions,
        'cycle_subscriptions': cycle_subscriptions,
        'books': books,
        'form': form,
        'userpreferences': preferences,
        'title': 'Профиль',

        'favorite_authors': favorite_authors, 
        'favorite_genres': favorite_genres,
        'disliked_genres': disliked_genres,
        'favorite_tags': favorite_tags,
        'disliked_tags': disliked_tags,
    }

    return render(request, 'profile.html', context)

 
 







@login_required
def cart(request):
    cart_items = UserBookStatus.objects.filter(user=request.user, status=UserBookStatus.STATUS_CART).select_related('book')
    books = []
    for item in cart_items:
        book = item.book
        book.in_cart = True
        book.in_bookmarks = UserBookStatus.objects.filter(user=request.user, book=book, status=UserBookStatus.STATUS_WISHLIST).exists()
        books.append(book)
    return render(request, 'cart.html', {'books': books, 'title': 'Корзина'})


@login_required
def bookmarks(request):
    bookmarks_items = UserBookStatus.objects.filter(user=request.user, status=UserBookStatus.STATUS_WISHLIST).select_related('book')
    books = []
    for item in bookmarks_items:
        book = item.book
        book.in_bookmarks = True
        book.in_cart = UserBookStatus.objects.filter(user=request.user, book=book, status=UserBookStatus.STATUS_CART).exists()
        books.append(book)
    context = {
        'books': books,
        'title': 'Закладки',
    }
    return render(request, 'bookmarks.html', context)


 


def registration(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'Пользователь с таким логином уже существует!'}, status=400)
        if password1 != password2:
            return JsonResponse({'error': 'Пароли не совпадают!'}, status=400)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return JsonResponse({'success': 'Регистрация успешна!'})
        else:
            return JsonResponse({'error': form.errors.as_json()}, status=400)
    else:
        form = SignUpForm()
    return render(request, 'home.html', {'form': form, 'user': request.user})
 