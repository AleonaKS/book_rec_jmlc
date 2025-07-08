import json
import os
import django
import logging
from django.utils.text import slugify 

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'books_site.settings')
django.setup()
 
from books.models import Book, Author, Genre, Tag, Series, Publisher, Cycle
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_or_create_slugged(model, name):
    if not name:
        return None
    slug_base = slugify(name)
    slug = slug_base
    num = 1
    while model.objects.filter(slug=slug).exists():
        slug = f"{slug_base}-{num}"
        num += 1
    obj, created = model.objects.get_or_create(name=name, defaults={'slug': slug})
    if not created and obj.slug != slug: 
        obj.slug = slug
        obj.save()
    return obj

def import_books(file_path):
    with open(file_path, 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)

    imported_isbns = set()

    for book_data in data:
        try:
            isbn_raw = book_data.get('isbn')
            if isinstance(isbn_raw, list) and isbn_raw:
                isbn = isbn_raw[0]   
            elif isinstance(isbn_raw, str):
                isbn = isbn_raw
            else:
                isbn = None
            if not isbn:
                continue
            if isbn in imported_isbns:
                continue
            imported_isbns.add(isbn)
 
            authors_raw = book_data.get('author') or []
            if isinstance(authors_raw, list):
                authors_list = [a.strip().rstrip(',') for a in authors_raw if a.strip()]
            elif isinstance(authors_raw, str):
                authors_list = [a.strip().rstrip(',') for a in authors_raw.split(',') if a.strip()]
            else:
                authors_list = []

            author_objs = [get_or_create_slugged(Author, name) for name in authors_list if name]
            author_objs = [a for a in author_objs if a]
 
            genre_name = book_data.get('genre')
            genre_obj = get_or_create_slugged(Genre, genre_name) if genre_name else None
 
            publisher_name = book_data.get('publisher')
            publisher_obj = get_or_create_slugged(Publisher, publisher_name) if publisher_name else None
 
            tags_raw = book_data.get('tags') or []
            tag_objs = [get_or_create_slugged(Tag, name) for name in tags_raw if name]
            tag_objs = [t for t in tag_objs if t]
 
            series_name = book_data.get('series')
            series_obj = get_or_create_slugged(Series, series_name) if series_name else None

            cycle_name = book_data.get('cycle')
            cycle_obj = get_or_create_slugged(Cycle, cycle_name) if cycle_name else None

            try:
                book_number_in_cycle = int(book_data.get('book_number_in_cycle') or 0)
            except Exception:
                book_number_in_cycle = None

            try:
                year = int(book_data.get('year_of_publishing') or 0)
            except Exception:
                year = 0

            try:
                pages = int(str(book_data.get('number_of_pages') or '0').replace('\xa0', '').strip())
            except Exception:
                pages = 0

            try:
                price = int(str(book_data.get('price') or '0').replace('\xa0', '').strip())
            except Exception:
                price = 0

            book_instance = Book(
                isbn=isbn,
                title=book_data.get('title') or '',
                soon=bool(book_data.get('soon', False)),
                new=bool(book_data.get('new', False)),
                cycle=cycle_obj,
                publisher=publisher_obj,
                series=series_obj,
                genre=genre_obj,
                year_of_publishing=year,
                number_of_pages=pages,
                book_number_in_cycle=book_number_in_cycle if book_number_in_cycle > 0 else None,
                age_restriction=book_data.get('age_restriction') or None,
                cover_type=book_data.get('cover_type') or 'неизвестно',
                description=book_data.get('description') or '',
                rating_chitai_gorod=float(book_data.get('rating_chitai_gorod') or 0),
                votes_chitai_gorod=int(book_data.get('rating_count_chitai_gorod') or 0),
                price=price,
                image_link=book_data.get('image_link') or '',
            )
            book_instance.save()

            if author_objs:
                book_instance.author.set(author_objs)
            if tag_objs:
                book_instance.tags.set(tag_objs)
            logger.info(f'Книга "{book_instance.title}" импортирована успешно!')
        except Exception as e:
            logger.error(f'Ошибка импорта книги "{book_data.get("title", "unknown")}": {e}')


if __name__ == '__main__': 
    json_file_path = 'scraper/parsing_books/spiders/books.json'
    import_books(json_file_path)
