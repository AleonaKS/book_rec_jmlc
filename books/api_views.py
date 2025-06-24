from rest_framework.decorators import permission_classes, api_view, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from haystack.query import SearchQuerySet
from .serializers import BookSerializer
from rest_framework import status
from django.shortcuts import get_object_or_404 
from django.utils import timezone 
import logging
logger = logging.getLogger(__name__)
# from django.views.decorators.csrf import csrf_exempt
  
from books.models import Book, BookRating, BookView, UserBookStatus
from .recommendations.collaborative import get_recommendations_for_user_user_based   


@api_view(['GET'])
def user_recommendations_api(request, user_id): 
    recommended_books = get_recommendations_for_user_user_based(user_id, top_n=10)
    serializer = BookSerializer(recommended_books, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])  
def autocomplete_books(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return Response([])  
    sqs = SearchQuerySet().autocomplete(content_auto=query)[:10]
    results = []
    for res in sqs:
        book = res.object
        if book:
            results.append({
                'id': book.id,
                'title': book.title,
                'author': ', '.join(author.name for author in book.author.all())
            })
    return Response(results)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_rate(request, book_id):
    try:
        rating_value = int(request.data.get('rating', 0))
    except (TypeError, ValueError):
        return Response({'error': 'Некорректный рейтинг'}, status=status.HTTP_400_BAD_REQUEST)

    if rating_value < 1 or rating_value > 5:
        return Response({'error': 'Рейтинг должен быть от 1 до 5'}, status=status.HTTP_400_BAD_REQUEST)

    book = get_object_or_404(Book, id=book_id)

    rating_obj, created = BookRating.objects.update_or_create(
        user=request.user,
        book=book,
        defaults={'rating': rating_value}
    )
    return Response({'message': 'Оценка сохранена'})

 

@api_view(['POST'])
@permission_classes([AllowAny]) 
def record_book_view(request):
    data = request.data
    book_id = data.get('book_id')
    print('book_id:', book_id)  
    duration = data.get('duration_seconds', 0)
    scroll = data.get('scroll_depth')

    if not book_id:
        return Response({'status': 'error', 'message': 'book_id is required'}, status=400)
    try:
        book = Book.objects.get(id=book_id)
    except Book.DoesNotExist:
        return Response({'status': 'error', 'message': 'Book not found'}, status=404)

    user = request.user if request.user.is_authenticated else None

    if user is None:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key 

        book_view_qs = BookView.objects.filter(user__isnull=True, session_key=session_key, book=book)
        if book_view_qs.exists():
            book_view = book_view_qs.first()
            book_view.duration_seconds = (book_view.duration_seconds or 0) + (data.get('duration_seconds', 0) or 0)
            book_view.viewed_at = timezone.now()
            scroll = data.get('scroll_depth')
            if scroll is not None:
                book_view.scroll_depth = scroll
            book_view.save()
            print(f"Обновлен BookView для сессииn {session_key} и книги {book_id}")
        else:
            BookView.objects.create(
                user=None,
                session_key=session_key,
                book=book,
                viewed_at=timezone.now(),
                duration_seconds=data.get('duration_seconds', 0),
                scroll_depth=data.get('scroll_depth')
            )
            print(f"Создан BookView для сессии {session_key} и книги {book_id}")

        user_views = BookView.objects.filter(user__isnull=True, session_key=session_key).order_by('-viewed_at')
    else:
        book_view, created = BookView.objects.get_or_create(
            user=user,
            book=book,
            defaults={
                'viewed_at': timezone.now(),
                'duration_seconds': data.get('duration_seconds', 0),
                'scroll_depth': data.get('scroll_depth')
            }
        )
        if not created:
            book_view.duration_seconds = (book_view.duration_seconds or 0) + (data.get('duration_seconds', 0) or 0)
            book_view.viewed_at = timezone.now()
            scroll = data.get('scroll_depth')
            if scroll is not None:
                book_view.scroll_depth = scroll
            book_view.save()
            print(f"Обновлен BookView для пользователя {user.id} и книги {book_id}")
        else:
            print(f"Создан BookView для пользователя {user.id} и книги {book_id}")

        user_views = BookView.objects.filter(user=user).order_by('-viewed_at')

    # Ограничиваем до 50 записей
    if user_views.count() > 50:
        to_delete = user_views[50:]
        to_delete.delete()
    last_20_books_ids = user_views.values_list('book_id', flat=True).distinct()[:20]
    # Удаляем записи вне последних 20 с duration < 30 сек
    old_views = user_views.exclude(book_id__in=last_20_books_ids)
    short_duration_views = old_views.filter(duration_seconds__lt=30)
    short_duration_views.delete()

    return Response({'status': 'ok'})




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart(request):
    logger.info("Корзина вызвана")
    book_id = request.data.get('book_id')
    if not book_id:
        return Response({'error': 'book_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    book = get_object_or_404(Book, id=book_id)
    user = request.user 
    obj, created = UserBookStatus.objects.update_or_create(
        user=user,
        book=book,
        defaults={'status': UserBookStatus.STATUS_CART}
    ) 
    return Response({'detail': 'Книга добавлена в корзину'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_bookmarks(request):
    logger.info("Закладки вызваны")
    print("Закладки")
    book_id = request.data.get('book_id')
    if not book_id:
        return Response({'error': 'book_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    book = get_object_or_404(Book, id=book_id)
    user = request.user 
    obj, created = UserBookStatus.objects.update_or_create(
        user=user,
        book=book,
        defaults={'status': UserBookStatus.STATUS_WISHLIST}
    ) 
    return Response({'detail': 'Книга добавлена в закладки'}, status=status.HTTP_200_OK)