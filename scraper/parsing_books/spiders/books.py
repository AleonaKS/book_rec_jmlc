import scrapy
import json
import re
import logging

logging.getLogger('scrapy.core.scraper').setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)  

class NewBooksSpiderSpider(scrapy.Spider): 
    name = "books"
    allowed_domains = ["chitai-gorod.ru"]
    custom_settings = { 'LOG_LEVEL': 'INFO' }
    start_urls = [
        f"https://www.chitai-gorod.ru/catalog/books/hudozhestvennaya-literatura-110001?page={page}"
        for page in range(1, 20)
    ]

    collected_books = {}
    duplicate_count = 0

    def parse(self, response):
        books = response.css('article.product-card')
        for book in books:
            link = book.css('a.product-card__title::attr(href)').get()
            rating_text = book.css('div.product-rating::attr(title)').get()
            rating = None
            if rating_text:
                match = re.search(r'([\d.]+)', rating_text)
                if match:
                    rating = float(match.group(1))

            rating_count_text = book.css('span.product-rating__votes::text').get()
            rating_count = int(rating_count_text) if rating_count_text and rating_count_text.isdigit() else None

            yield response.follow(
                link,
                callback=self.parse_book_info,
                meta={
                    'rating': rating,
                    'rating_count': rating_count
                }
            )

        next_page = response.css('a.pagination__next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_book_info(self, response):
        def safe_get_text(element):
            return element.strip() if element else None 

        def get_genre(response):
            genres = response.css('.breadcrumbs__item span[itemprop="name"]::text').getall()
            return genres[-2].strip() if len(genres) >= 2 else None

        def get_tags(response):
            tags = response.css('.product-description-short__tag .chg-app-button__content div::text').getall()
            return [safe_get_text(tag) for tag in tags]

        def get_authors(response):
            authors = response.css('.product-info-authors__author::text').getall()
            return [a.strip() for a in authors if a.strip()]

        def get_cycle_book(response):
            cycle_book = safe_get_text(response.css('.product-cycle__header::text').get())
            return cycle_book.replace('содержание цикла ', '') if cycle_book else None

        def get_description(response):
            parts = response.css('.detail-description__text ::text').getall()
            return '\n'.join(part.strip() for part in parts if part.strip()) if parts else None

        def get_price(response):
            price_text = response.css('.product-offer-price__old-price::text').get()
            return price_text.replace('₽', '').strip() if price_text else None

        title = safe_get_text(response.css('h1[itemprop="name"]::text').get())
        author = get_authors(response)

        if not title or not author:
            return

        book_key = (title, ', '.join(author))
        if book_key in self.collected_books:
            self.duplicate_count += 1
            return   

        book_info = {
            'isbn': safe_get_text(response.css('.product-detail-features__item-title:contains("ISBN") + .product-detail-features__item-value::text').get()),
            'title': title,
            'author': author,
            'soon': bool(response.css('a.product-info-badge--green:contains("Скоро")')),
            'new': bool(response.css('a.product-info-badge--lemon:contains("Новинка")')),
            'genre': get_genre(response),
            'tags': get_tags(response),
            'cycle_book': get_cycle_book(response),
            'series': safe_get_text(response.css('a[href*="/series/"]::text').get()),
            'publisher': safe_get_text(response.css('a[itemprop="publisher"]::text').get()),
            'the_year_of_publishing': safe_get_text(response.css('span[itemprop="datePublished"]::text').get()),
            'number_of_pages': safe_get_text(response.css('span[itemprop="numberOfPages"]::text').get()),
            'age_restriction': safe_get_text(response.css('span[itemprop="typicalAgeRange"]::text').get()),
            'cover_type': safe_get_text(response.css('span[itemprop="bookFormat"]::text').get()),
            'description': get_description(response),
            'rating_chitai_gorod': response.meta.get('rating'),
            'rating_count_chitai_gorod': response.meta.get('rating_count'),
            'price': get_price(response),
            'image_link': response.css('.product-info-gallery__poster::attr(src)').get(),
        }

        self.collected_books[book_key] = book_info
        yield book_info

        if len(self.collected_books) % 10 == 0:
            with open('books.json', 'w', encoding='utf-8') as f:
                json.dump(list(self.collected_books.values()), f, ensure_ascii=False, indent=2)
            self.logger.info(f"Сохранено {len(self.collected_books)} книг")
