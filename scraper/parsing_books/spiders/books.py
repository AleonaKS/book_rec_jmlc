import scrapy
import re
import time 

class NewBooksSpiderSpider(scrapy.Spider):
    name = "books"
    allowed_domains = ["chitai-gorod.ru"]
    start_urls = ["https://www.chitai-gorod.ru/catalog/books/hudozhestvennaya-literatura-110001?page=1"]
    handle_httpstatus_list = [403]
    custom_settings = {
        'LOG_LEVEL': 'INFO',
        'FEEDS': {
            'books.json': {
                'format': 'json',
                'encoding': 'utf8',
                'indent': 2,
                'overwrite': True,
            }
        }
    }
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collected_books = {}
        self.duplicate_count = 0
        self.max_pages = 2
        self.current_page = 1 

    def start_requests(self):
        time.sleep(5)
        self.logger.info(f"Старт паука, стартовые URL: {self.start_urls}")
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)




    def parse(self, response):
        if response.status == 403:
            self.logger.warning(f"Получен 403 Forbidden на {response.url}, делаем паузу 20 секунд...")
            time.sleep(20)  
            yield scrapy.Request(response.url, callback=self.parse, dont_filter=True)
            return

        books = response.css('article.product-card')
        self.logger.info(f"Найдено книг на странице {response.url}: {len(books)}")
        for book in books:
            link = book.css('a.product-card__title::attr(href)').get()
            rating = book.css('div.product-card__feedback div.product-rating::attr(title)').get()
            rating_count_text = book.css('div.product-card__feedback span.product-rating__votes::text').get()
            rating_count = int(re.sub(r'\D', '', rating_count_text)) if rating_count_text else None
            if link:
                yield response.follow(
                    link,
                    callback=self.parse_book_info,
                    meta={
                        'rating': rating,
                        'rating_count': rating_count
                    }
                )
            else:
                self.logger.warning("Не удалось получить ссылку на книгу!")
        next_page = response.css('a.chg-app-pagination__button-next::attr(href)').get()
        if next_page and self.current_page < self.max_pages:
            self.current_page += 1
            self.logger.info(f"Переход на следующую страницу: {next_page}")
            yield response.follow(next_page, self.parse)
        else:
            self.logger.info("Следующая страница не найдена или достигнут лимит страниц, парсинг завершён.")


    def parse_book_info(self, response):
        if response.status == 403:
            self.logger.warning(f"Получен 403 Forbidden на {response.url}, делаем паузу 20 секунд...")
            time.sleep(20)
            yield scrapy.Request(response.url, callback=self.parse_book_info, meta=response.meta, dont_filter=True)
            return

        def safe_get_text(element):
            return element.strip() if element else None 
        
        def to_type(value, cast_type):
            try:
                if isinstance(value, str):
                    value = value.strip()
                return cast_type(value)
            except (TypeError, ValueError):
                return None



        def get_isbn(response):
            isbn_raw = response.css('li.product-properties-item span[itemprop="isbn"] span::text').get()
            if isbn_raw:
                return [isbn.strip() for isbn in isbn_raw.split(',')]
            else:
                return [] 
        
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


        def get_authors(response):
            authors = response.css('ul.product-authors li[itemprop="author"] a::text').getall()
            return [a.strip() for a in authors if a.strip()]
        
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
            return
 

        book_info = {
            'isbn': get_isbn(response),
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
            'rating_chitai_gorod': to_type(response.meta.get('rating'), float),
            'rating_count_chitai_gorod': to_type(response.meta.get('rating_count'), int),
            'price': to_type(get_price(response), int),
            'image_link': response.css('div.product-detail-page__media img.product-preview__placeholder::attr(src)').get(),
        }

        book_key = (title, ', '.join(author))
        existing = self.collected_books.get(book_key) 
        rating_count = to_type(response.meta.get('rating_count'), int) or 0

        if existing:
            existing_rating_count = to_type(existing.get('rating_count_chitai_gorod'), int) or 0
            if rating_count > existing_rating_count:
                self.collected_books[book_key] = book_info
                self.logger.info(f"Обновлена книга {title} с большим количеством отзывов: {rating_count} > {existing_rating_count}")
                yield book_info
            else:
                self.duplicate_count += 1
                self.logger.info(f"Дубликат книги пропущен: {book_key}")
        else:
            self.collected_books[book_key] = book_info
            yield book_info


    def closed(self, reason):
        self.logger.info(f"Всего собрано уникальных книг: {len(self.collected_books)}")
        self.logger.info(f"Количество пропущенных дубликатов: {self.duplicate_count}")
