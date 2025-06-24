import os
import re
import time
import json
import random
import logging
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
handlers=[logging.FileHandler("scraper.log", encoding="utf-8"),logging.StreamHandler()])

class LivelibScraper:
    def __init__(self, books, use_first_result=False):
        self.books = books
        self.results = {}
        self.use_first_result = use_first_result


    def save_book_result(self, key, data):
        with open('reviews_results_new.jsonl', 'a', encoding='utf-8') as f:
            json_line = json.dumps({str(key): data}, ensure_ascii=False)
            f.write(json_line + '\n')


    def scroll_randomly(self, page, min_scrolls=1, max_scrolls=3, min_delay=0.5, max_delay=1.5):
        scrolls = random.randint(min_scrolls, max_scrolls)
        for _ in range(scrolls):
            scroll_y = random.randint(200, 1000)
            page.evaluate(f"window.scrollBy(0, {scroll_y});")
            time.sleep(random.uniform(min_delay, max_delay))


    def extract_total_votes(self, page):
        rating_button = page.locator("button.bc-rating__btn.rating-button")
        rating_button.hover()
        try: 
            locator = page.locator("span.bc-rating__medium-qty.bc-rating__medium-qty_type_total")
            locator.wait_for(timeout=20000)   
            text = locator.inner_text().strip().replace('\xa0', '').replace(' ', '')
            total_votes = int(text)
        except Exception as e:
            print("Ошибка при получении количества оценок:", e)
        return total_votes


    def extract_book_rating_from_button(self, page):
        try:
            rating_btn = page.query_selector('button.bc-rating__btn')
            if not rating_btn:
                return None
            title_attr = rating_btn.get_attribute('title')
            if not title_attr:
                return None
            match = re.search(r'Рейтинг\s+([\d.,]+)', title_attr)
            if match:
                raw_rating = match.group(1).replace(',', '.')
                return round(float(raw_rating), 2)
        except Exception as e:
            logging.warning(f"Не удалось извлечь рейтинг: {e}")
        return None


    def extract_isbn(self, book):
        isbn_raw = book.get('isbn')
        if isinstance(isbn_raw, list) and isbn_raw:
            return isbn_raw[0]
        elif isinstance(isbn_raw, str):
            return isbn_raw
        return None

    def clean_str(self, s):
        return re.sub(r'[«»"\']', '', s.lower()).strip()

    def titles_match(self, title1, title2): 
        t1 = self.clean_str(title1)
        t2 = self.clean_str(title2)
        return t1 in t2 or t2 in t1

    def authors_match(self, author1, author2):
        a1 = author1.lower()
        a2 = author2.lower()
        return a1 in a2 or a2 in a1


    def parse_reviews(self, page, max_pages=3):
            reviews = []
            pages_parsed = 0
            while pages_parsed < max_pages:
                review_cards = page.query_selector_all('div.review-card.lenta__item')
                for card in review_cards:
                    user_el = card.query_selector('a.header-card-user__name span')
                    rating_el = card.query_selector('span.lenta-card__mymark')
                    date_el = card.query_selector('p.lenta-card__date')
                    user = user_el.inner_text().strip() if user_el else None
                    rating = rating_el.inner_text().strip() if rating_el else None
                    date_text = date_el.inner_text().strip() if date_el else None
                    if pages_parsed == 0:
                        # На первой странице открываем страницу с каждой рецензией
                        full_link_el = card.query_selector('a.lenta-card__full-text-review-link')
                        if full_link_el:
                            href = full_link_el.get_attribute('href')
                            full_review_url = 'https://www.livelib.ru' + href

                            review_page = page.context.new_page()
                            review_page.goto(full_review_url, wait_until='load', timeout=60000)
                            review_page.wait_for_load_state('domcontentloaded', timeout=60000)
                            time.sleep(random.uniform(2, 4))
                            self.scroll_randomly(review_page)

                            text_els = review_page.query_selector_all('div.lenta-card__text p')
                            text = "\n".join([p.inner_text().strip() for p in text_els]) if text_els else None
                            review_page.close()
                        else:
                            text = None
                    else:
                        # С остальных страниц — берём только ник и оценку
                        text = None

                    reviews.append({
                        'user': user,
                        'rating': rating,
                        'date': date_text,               
                        'text': text
                    })

                    time.sleep(random.uniform(1, 2))
 
                pagination_div = page.query_selector('div#book-reviews-pagination div.pagination')
                if not pagination_div:
                    break

                active_span = pagination_div.query_selector('span.pagination__page--active')
                if not active_span:
                    break

                try:
                    current_page_num = int(active_span.inner_text().strip())
                except Exception:
                    break

                next_page_num = current_page_num + 1
                next_page_link = None
                page_links = pagination_div.query_selector_all('a.pagination__page')
                for a in page_links:
                    try:
                        page_num = int(a.inner_text().strip())
                        if page_num == next_page_num:
                            next_page_link = a.get_attribute('href')
                            break
                    except Exception:
                        continue

                if not next_page_link:
                    break

                next_url = 'https://www.livelib.ru' + next_page_link
                page.goto(next_url, wait_until='load', timeout=60000)
                page.wait_for_load_state('domcontentloaded', timeout=60000)
                time.sleep(random.uniform(2, 4))
                self.scroll_randomly(page)
                pages_parsed += 1

            return reviews


    def find_book_url(self, page, book):
        try:
            page.wait_for_selector('div.object-wrapper.object-wrapper-outer.object-edition', timeout=10000)
        except Exception:
            return None, None

        results = page.query_selector_all('div.object-wrapper.object-wrapper-outer.object-edition')
        if not results:
            return None, None

        if self.use_first_result:
            first_result = results[0]
            rating_el = first_result.query_selector('span.rating-value')
            book_rating = rating_el.inner_text().strip() if rating_el else None
            href_el = first_result.query_selector('div.ll-redirect a')
            if href_el:
                href = href_el.get_attribute('href')
                return href, book_rating
            return None, None
        else:
            for res in results:
                rating_el = res.query_selector('span.rating-value')
                book_rating = rating_el.inner_text().strip() if rating_el else None
                title_site_el = res.query_selector('div.brow-title a.title')
                author_site_el = res.query_selector('a.description')
                if not title_site_el or not author_site_el:
                    continue
                title_text = title_site_el.inner_text().strip()
                author_text = author_site_el.inner_text().strip()

                if self.titles_match(book['title'], title_text) and self.authors_match(book['author'], author_text):
                    href_el = res.query_selector('div.ll-redirect a')
                    if href_el:
                        href = href_el.get_attribute('href')
                        return href, book_rating
        return None, None


    def process_book(self, page, book):
        isbn = self.extract_isbn(book)
        book_rating = None
        found_url = None

        if isbn:
            search_url = f"https://www.livelib.ru/find/{quote_plus(isbn)}" 
            page.goto(search_url, wait_until='load', timeout=60000)
            found_url, _ = self.find_book_url(page, book)

        if not found_url:
            query = quote_plus(book['title'])
            search_url = f"https://www.livelib.ru/find/{query}" 
            page.goto(search_url, wait_until='load', timeout=60000)
            found_url, _ = self.find_book_url(page, book)

        if not found_url:
            logging.error(f"Книга '{book['isbn']}' :'{book['title']}' автора '{book['author']}' не найдена на сайте")
            self.results[isbn or book['title']] = {'error': 'Not found'}
            return

        book_url = page.url.split('/find/')[0] + found_url 
        page.goto(book_url, wait_until='load', timeout=60000)
        time.sleep(random.uniform(2, 4))
        self.scroll_randomly(page)
 
        book_rating = self.extract_book_rating_from_button(page)
        total_votes = self.extract_total_votes(page)

        reviews_tab = page.query_selector('a.bc-detailing-reviews')
        if not reviews_tab:
            logging.error(f"Вкладка с рецензиями не найдена для книги '{book['title']}'")
            self.results[isbn or book['title']] = {'error': 'Reviews tab not found'}
            return

        reviews_url = page.url.split('/book/')[0] + reviews_tab.get_attribute('href') 
        page.goto(reviews_url, wait_until='load', timeout=60000)
        page.wait_for_load_state('domcontentloaded', timeout=60000)
        self.scroll_randomly(page)

        reviews = self.parse_reviews(page)
        key = isbn if isbn else book['title']
        self.results[str(key)] = {
            'rating': book_rating,
            'votes': total_votes,
            'reviews': reviews
        }
        self.save_book_result(key, self.results[str(key)])


    def run(self):
        start_all = time.time()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(viewport={'width': 1280, 'height': 800})
                page = context.new_page()

                found_count = 0
                not_found_count = 0

                for book in self.books:
                    try: 
                        start_time = time.time()
                        self.process_book(page, book)
                        elapsed = time.time() - start_time
                        logging.info(f"Завершена обработка: {book['title']} за {elapsed:.2f} сек")
                        isbn = self.extract_isbn(book)
                        key = isbn if isbn else book['title']
                        if 'reviews' in self.results.get(str(key), {}):
                            found_count += 1
                        else:
                            not_found_count += 1 
                    except Exception as e:
                        logging.error(f"Ошибка при обработке книги '{book['title']}': {e}")
                        not_found_count += 1

                browser.close()
        except KeyboardInterrupt:
            logging.warning("Прерывание пользователем. Сохранение текущих результатов...")

        finally:
            total_time = time.time() - start_all
            logging.info(f"Общее время выполнения: {total_time:.2f} сек")
            logging.info(f"Обработано книг: {len(self.results)}")
            logging.info(f"Найдено и собрано отзывов: {len([r for r in self.results.values() if 'reviews' in r])}")
            with open('reviews_results_new.json', 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=4)
            logging.info("Результаты сохранены.")

 
if __name__ == "__main__": 
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    json_path = os.path.join(project_root, 'parsing_books/spiders/books.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        books = json.load(f)
    # установка use_first_result=True, чтобы брать первую книгу из результатов
    scraper = LivelibScraper(books, use_first_result=True)
    scraper.run()
