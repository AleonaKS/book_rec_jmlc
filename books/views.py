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
from .models import UserPreferences, FavoriteAuthors, FavoriteGenres, FavoriteTags, DislikedGenres, DislikedTags
from books.recommendations.base_recommendations import recommendations_split, recommendations_for_anonymous, recommendations_for_user_without_preferences
from books.recommendations.hybrid import hybrid_recommendations_for_user, hybrid_recommendations_for_book

logger = logging.getLogger(__name__)
 

def switch_keyboard_layout(text):
    layout_en = 'qwertyuiop[]asdfghjkl;\'zxcvbnm,./`QWERTYUIOP{}ASDFGHJKL:"ZXCVBNM<>?~'
    layout_ru = 'йцукенгшщзхъфывапролджэячсмитьбю.ёЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,Ё'
    assert len(layout_en) == len(layout_ru), "Раскладки должны быть одинаковой длины"
    trans_table = str.maketrans(layout_en + layout_ru, layout_ru + layout_en)
    return text.translate(trans_table)


@require_GET
def search_books(request):
    query = request.GET.get('q', '').strip()
    alt_query = switch_keyboard_layout(query) if query else ''
    sort = request.GET.get('sort_by', '')
    filtered_books = []
    book_filter = None

    if query:
        sqs_title_main = SearchQuerySet().autocomplete(content_auto=query)
        sqs_title_alt = SearchQuerySet().autocomplete(content_auto=alt_query) if alt_query else SearchQuerySet().none()
        sqs_author_main = SearchQuerySet().autocomplete(author_auto=query)
        sqs_author_alt = SearchQuerySet().autocomplete(author_auto=alt_query) if alt_query else SearchQuerySet().none()

        sqs = (sqs_title_main | sqs_title_alt | sqs_author_main | sqs_author_alt).load_all()
        books = [res.object for res in sqs if res.object is not None][:100]
        book_ids = [book.id for book in books]

        book_filter = BookFilter(request.GET, queryset=Book.objects.filter(id__in=book_ids))
        filtered_qs = book_filter.qs

        if sort == 'popularity':
            filtered_qs = filtered_qs.order_by('-popularity_score')
        elif sort == 'newness':
            filtered_qs = filtered_qs.order_by('-year_of_publishing')

        filtered_books = list(filtered_qs)
    else:
        qs = Book.objects.all()
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



def home_view(request):
    popular_books, new_books, soon_books = None, None, None
    if request.user.is_authenticated:
        user_views = BookView.objects.filter(user=request.user).order_by('-viewed_at')
        user = request.user
        recommended_books = hybrid_recommendations_for_user(user, top_n=30)
        try:
            prefs = user.userpreferences
            favorite_genres = prefs.favorite_genres.all().values_list('id', flat=True)
            favorite_tags = prefs.favorite_tags.all().values_list('id', flat=True)
            # recommended_books = hybrid_recommendations_for_user(user, top_n=30)
            popular_books, new_books, soon_books = recommendations_split(user, list(favorite_genres), list(favorite_tags), top_n=30)
        except UserPreferences.DoesNotExist:
            popular_books, new_books, soon_books = recommendations_for_user_without_preferences(user, top_n=30)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        user_views = BookView.objects.filter(user__isnull=True, session_key=session_key).order_by('-viewed_at')
        recommended_books = Book.objects.all()
        popular_books, new_books, soon_books = recommendations_for_anonymous(session_key)

    last_20_book_ids = list(user_views.values_list('book_id', flat=True).distinct()[:20])
    books = list(Book.objects.filter(id__in=last_20_book_ids))
    last_books = sorted(books, key=lambda b: last_20_book_ids.index(b.id))

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
}


def books_by_category(request, category_slug=None):
    books = Book.objects.all()
    category_name = 'Книги'

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

    context = {
        'books': books,
        'category_name': category_name,
        'csrf_token': get_token(request),
    }
    return render(request, 'books_by_category.html', context)


# ==========================


@login_required
def profile(request):
    user = request.user
    preferences, created = UserPreferences.objects.get_or_create(user=user)
    user_ratings_subquery = BookRating.objects.filter(
        user=request.user,
        book=OuterRef('pk')
    ).values('rating')[:1]
    books = Book.objects.annotate(
        user_rating=Subquery(user_ratings_subquery)
    ).filter(user_rating__isnull=False)
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=preferences, user=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Настройки сохранены')
            return redirect('profile')
    else:
        form = UserPreferencesForm(instance=preferences, user=user)
    context = {
        'books': books,
        'form': form, 
        'userpreferences': preferences,
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



def signup(request):
    return render(request, 'home.html', {'user': request.user})


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
    return render(request, 'home.html', {'form': form})

