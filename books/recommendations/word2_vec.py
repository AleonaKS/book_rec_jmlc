import re
import numpy as np
from books.models import BookVector, Book
from gensim.models import Word2Vec 


def compute_and_store_word2vec_vectors(vector_size=100, window=5, min_count=2, workers=4):
    corpus, books = prepare_corpus()
    if not corpus:
        print("Корпус пуст")
        return
 
    model = Word2Vec(sentences=corpus, vector_size=vector_size, window=window,
                     min_count=min_count, workers=workers)
 
    for book, tokens in zip(books, corpus):
        vectors = [model.wv[word] for word in tokens if word in model.wv]
        if vectors:
            book_vector = np.mean(vectors, axis=0)
        else:
            book_vector = np.zeros(vector_size)

        BookVector.objects.update_or_create(
            book=book,
            defaults={'vector': book_vector.tolist()}
        ) 



def get_similar_books_by_w2v(target_book_id, top_n=10):
    try:
        target_vector_obj = BookVector.objects.get(book_id=target_book_id)
    except BookVector.DoesNotExist:
        return []

    target_vector = target_vector_obj.vector
    if not target_vector:
        return []

    vectors_qs = BookVector.objects.exclude(book_id=target_book_id).exclude(vector__isnull=True)
    book_vectors = [(bv.book_id, bv.vector) for bv in vectors_qs if bv.vector]

    target_vec_np = np.array(target_vector)
    target_norm = np.linalg.norm(target_vec_np)
    if target_norm == 0:
        return []

    similarities = []
    for book_id, vec in book_vectors:
        vec_np = np.array(vec)
        norm = np.linalg.norm(vec_np)
        if norm == 0:
            continue
        sim = np.dot(target_vec_np, vec_np) / (target_norm * norm)
        similarities.append((book_id, sim))

    similarities.sort(key=lambda x: x[1], reverse=True)
    top_similar = similarities[:top_n]

    book_ids = [book_id for book_id, _ in top_similar]
    books = Book.objects.filter(id__in=book_ids)
    books_dict = {book.id: book for book in books}

    result = []
    for book_id, sim in top_similar:
        book = books_dict.get(book_id)
        if book:
            result.append({'book': book, 'similarity': sim})
    return result


def tokenize(text):  # Простая токенизация: по словам, в нижний регистр, только буквы и цифры
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return tokens

def prepare_corpus():
    """
    Собираем тексты для обучения word2vec: описание + отзывы каждой книги.
    Возвращает список списков токенов (корпус для обучения).
    """
    corpus = []
    books = Book.objects.prefetch_related('review_set').all()

    for book in books:
        # Собираем описание + все отзывы в один текст
        texts = [book.description or '']
        reviews = book.review_set.all()
        texts.extend([r.text or '' for r in reviews])
        full_text = ' '.join(texts)
        tokens = tokenize(full_text)
        if tokens:
            corpus.append(tokens)
    return corpus, books

 