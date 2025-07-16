import scrapy
import json
import re
import os
import time

class BookInfoFromISBNSpider(scrapy.Spider):
    name = "bookinfo_from_isbn"
    allowed_domains = ["chitai-gorod.ru"]

    custom_settings = {
        'LOG_LEVEL': 'INFO',
        'FEEDS': {
            'books_info_from_isbn.json': {
                'format': 'json',
                'encoding': 'utf8',
                'indent': 2,
                'overwrite': True,
            }
        }
    }

    def start_requests(self): 
        json_path = os.path.join(os.path.dirname(__file__), 'reviews_results_old_old.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.isbns = list(data.keys())
        self.reviews_data = data

        for isbn in self.isbns:
            search_url = f'https://www.chitai-gorod.ru/search?phrase={isbn}'
            yield scrapy.Request(search_url, callback=self.parse_search, meta={'isbn': isbn})

    def parse_search(self, response):
        isbn = response.meta['isbn']  
        books = response.css('article.product-card')
        if not books:
            self.logger.warning(f"Книга с ISBN {isbn} не найдена на chitai-gorod.ru")
            yield {
                'isbn': isbn,
                'error': 'Book not found on chitai-gorod.ru'
            }
            return
 
        book = books[0]

        link = book.css('a.product-card__title::attr(href)').get()
        rating = book.css('div.product-card__feedback div.product-rating::attr(title)').get()
        rating_count_text = book.css('div.product-card__feedback span.product-rating__votes::text').get()
        rating_count = int(re.sub(r'\D', '', rating_count_text)) if rating_count_text else None

        if link:
            yield response.follow(
                link,
                callback=self.parse_book_info,
                meta={
                    'isbn': isbn,
                    'rating': rating,
                    'rating_count': rating_count
                }
            )
        else:
            self.logger.warning(f"Ссылка на книгу с ISBN {isbn} не найдена.")
            yield {
                'isbn': isbn,
                'error': 'Book link not found in search results'
            }
         
    def parse_book_info(self, response):
        isbn = response.meta['isbn']
        rating = response.meta.get('rating')
        rating_count = response.meta.get('rating_count')

        def safe_get_text(element):
            return element.strip() if element else None
        
        def to_type(value, cast_type):
            try:
                if isinstance(value, str):
                    value = value.strip()
                return cast_type(value)
            except (TypeError, ValueError):
                return None

        def get_authors(response):
            authors = response.css('ul.product-authors li[itemprop="author"] a::text').getall()
            return [a.strip() for a in authors if a.strip()]

        def get_genre(response):
            genres = response.css('.breadcrumbs__item span[itemprop="name"]::text').getall()
            return genres[-2].strip() if len(genres) >= 2 else None

        def get_tags(response):
            tags = response.css('ul.product-tag-list li a.product-tag::text').getall() 
            seen = set()
            clean_tags = []
            for tag in tags:
                tag_clean = tag.strip() if tag else None
                if tag_clean and tag_clean not in seen:
                    seen.add(tag_clean)
                    clean_tags.append(tag_clean)
            return clean_tags

        def get_cycle_book(response): 
            subtitle = response.css('section.product-cycle h3.product-detail-page__subtitle::text').get()
            if subtitle:
                prefix = "Содержание цикла "
                if subtitle.startswith(prefix):
                    return subtitle[len(prefix):].strip()
                else:
                    return subtitle.strip()  

        def get_description(response):
            description = response.css('article.product-detail-page__detail-text[itemprop="description"]::text').getall()
            return ' '.join([d.strip() for d in description if d.strip()]) if description else None 

        def get_price(response):
            price_text = response.css('span.product-offer-price__old-text::text').get()
            if price_text: 
                price_digits = re.sub(r'\D', '', price_text)
                try:
                    return int(price_digits)
                except ValueError:
                    return None
            return None

        def get_book_number_in_cycle(response): 
            active_item = response.css('ol.product-cycle__list li.product-cycle__list-item svg.product-cycle__icon-active')
            if active_item: 
                parent_li = active_item.xpath('ancestor::li[1]')
                if parent_li:
                    link_text = parent_li.css('a.product-cycle__list-link::text').get()
                    if link_text: 
                        match = re.match(r'(\d+)\.', link_text.strip())
                        if match:
                            return int(match.group(1))
            return None

        title = response.css('h1[itemprop="name"].product-detail-page__title::text').get()
        if title:
            title = title.strip()
        author = get_authors(response)

        if not title or not author:
            self.logger.warning(f"Пропущена книга без названия или автора на странице: {response.url}")
            yield {
                'isbn': isbn,
                'error': 'Missing title or author',
                'url': response.url
            }
            return

        book_info = {
            'isbn': isbn,
            'title': title,
            'author': author,
            'soon': bool(response.css('a.product-badge.product-badge--saleSoon').re(r'Скоро')),
            'new': bool(response.css('a.product-badge.product-badge--new').re(r'Новинка')),
            'genre': get_genre(response),
            'tags': get_tags(response),
            'cycle': get_cycle_book(response),
            'book_number_in_cycle': get_book_number_in_cycle(response),
            'series': safe_get_text(response.css('li.product-properties-item span a[href*="/series/"]::text').get()), 
            'publisher': safe_get_text(response.css('li.product-properties-item span[itemprop="publisher"] a::text').get()),
            'year_of_publishing': to_type(safe_get_text(response.css('li.product-properties-item span[itemprop="datePublished"] span::text').get()), int),
            'number_of_pages': to_type(safe_get_text(response.css('li.product-properties-item:contains("Количество страниц") span[itemprop="numberOfPages"] span::text').get()), int),
            'age_restriction': safe_get_text(response.xpath('//li[contains(.,"Возрастные ограничения")]//span[@itemprop="typicalAgeRange"]/span/text()').get()),
            'cover_type': safe_get_text(response.xpath('//li[contains(.,"Тип обложки")]//span[@itemprop="bookFormat"]/span/text()').get()),
            'description': get_description(response),
            'rating_chitai_gorod': rating or self.reviews_data.get(isbn, {}).get('rating'),
            'rating_count_chitai_gorod': rating_count or self.reviews_data.get(isbn, {}).get('votes'),
            'price': get_price(response),
            'image_link': response.css('div.product-detail-page__media img.product-preview__placeholder::attr(src)').get(),
        }

        yield book_info
