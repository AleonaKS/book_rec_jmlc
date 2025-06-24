import json
import os
import django
import logging
import dateparser
from django.utils import timezone
 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'books_site.settings')
django.setup()
 
from books.models import Book, Review, BookRating
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  


from django.contrib.auth.models import User

def import_reviews(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)


        for isbn_key, book_data in data.items():
            if 'error' in book_data:
                logger.warning(f"Пропуск ISBN {isbn_key} из-за ошибки: {book_data['error']}")
                continue
 
            book = Book.objects.filter(isbn=isbn_key).first()

            if not book:
                logger.warning(f"Книга по ISBN {isbn_key} не найдена")
                continue

            rating_raw = book_data.get('rating')
            votes_raw = book_data.get('votes')       

            try:
                rating = float(rating_raw) if rating_raw is not None else None
            except (ValueError, TypeError):
                rating = None

            try:
                votes = int(votes_raw) if votes_raw is not None else None
            except (ValueError, TypeError):
                votes = None

            updated_fields = []
            if rating is not None:
                book.rating_livelib = rating
                updated_fields.append('rating_livelib')

            if votes is not None:
                book.votes_livelib = votes
                updated_fields.append('votes_livelib')

            if updated_fields:
                book.save(update_fields=updated_fields)

            reviews = book_data.get('reviews', [])
            for review_data in reviews:
                username = review_data.get('user')
                rating_review_raw = review_data.get('rating')
                date_str = review_data.get('date')   
                text = review_data.get('text')

                if not username:
                    logger.warning(f"Отзыв пропущен из-за отсутствия имени пользователя для книги {book.title}")
                    continue

                try:
                    rating_review = float(rating_review_raw) if rating_review_raw is not None else None
                except (ValueError, TypeError):
                    rating_review = None

                if date_str:
                    parsed_date = dateparser.parse(date_str, languages=['ru'])
                    if parsed_date is not None and timezone.is_naive(parsed_date):
                        parsed_date = timezone.make_aware(parsed_date)
                else:
                    parsed_date = None
 
                user_obj, created = User.objects.get_or_create(username=username)

                try:
                    if (text is None or text.strip() == '') and rating_review is not None: 
                        BookRating.objects.update_or_create(
                            book=book,
                            user=user_obj,
                            defaults={
                                'rating': rating_review,
                                'rated_at': parsed_date,
                            }
                        )
                    else: 
                        Review.objects.create(
                            book=book,
                            user=user_obj,
                            rating=rating_review,
                            review_date=parsed_date,
                            text=text,
                        )
                except Exception as e:
                    logger.error(f"Не удалось сделать запись книги {book.title}, пользователя {username}: {e}")

        logger.info('Рецензии успешно испортированы!')

    except Exception as e:
        logger.error(f'Произошла ошибка: {e}')
        raise


if __name__ == '__main__':
    json_file_path = 'scraper/parsing_books/spiders/reviews_results.json'
    import_reviews(json_file_path)
