# в процессе разработки "Topic Modeling" для выявления скрытых тем

import gensim
from gensim import corpora
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import nltk 
import numpy as np
from scipy.spatial.distance import cosine
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from transformers import AutoTokenizer, AutoModel
import torch

from books.models import Book, BookTopicVector, BookEmbedding, ReviewEmbedding, ReviewSentiment, Review  # импортируйте свои модели


def preprocess(text):
    stop_words = set(stopwords.words('russian'))
    lemmatizer = WordNetLemmatizer()

    tokens = gensim.utils.simple_preprocess(text, deacc=True)
    tokens = [lemmatizer.lemmatize(t) for t in tokens if t not in stop_words and len(t) > 2]
    return tokens


def train_lda_and_save(num_topics=20, no_below=5, no_above=0.5, passes=10):
 

    descriptions = list(Book.objects.values_list('description', flat=True))
    texts = [preprocess(desc or '') for desc in descriptions]

    dictionary = corpora.Dictionary(texts)
    dictionary.filter_extremes(no_below=no_below, no_above=no_above)
    corpus = [dictionary.doc2bow(text) for text in texts]

    lda = gensim.models.LdaModel(corpus, num_topics=num_topics, id2word=dictionary, passes=passes)

    lda.save('lda_model.model')
    dictionary.save('lda_dictionary.dict')

    # Сохраняем векторы тем в БД
    books = Book.objects.all()
    for book, bow in zip(books, corpus):
        topic_dist = lda.get_document_topics(bow, minimum_probability=0)
        vector = [0.0] * num_topics
        for topic_id, prob in topic_dist:
            vector[topic_id] = prob

        BookTopicVector.objects.update_or_create(
            book=book,
            defaults={
                'indices': [i for i, v in enumerate(vector) if v > 0],
                'values': [v for v in vector if v > 0]
            }
        )


def get_dense_topic_vector(book_topic_vector, num_topics=20):
    vector = [0.0] * num_topics
    for idx, val in zip(book_topic_vector.indices, book_topic_vector.values):
        vector[idx] = val
    return vector


def get_user_topic_vector(user, num_topics=20): 
    user_reviews = Review.objects.filter(user=user).select_related('book')
    topic_vectors = []
    for review in user_reviews:
        try:
            btv = review.book.topic_vector
            vec = get_dense_topic_vector(btv, num_topics)
            topic_vectors.append(np.array(vec))
        except BookTopicVector.DoesNotExist:
            continue
    if not topic_vectors:
        return None
    user_vec = np.mean(topic_vectors, axis=0)
    return user_vec


def recommend_books_by_topics(user, top_n=10, num_topics=20):
    user_vec = get_user_topic_vector(user, num_topics)
    if user_vec is None:
        return Book.objects.none()

    all_btv = BookTopicVector.objects.select_related('book').all()
    scores = []
    for btv in all_btv:
        vec = get_dense_topic_vector(btv, num_topics)
        dist = cosine(user_vec, vec)
        scores.append((dist, btv.book))
    scores.sort(key=lambda x: x[0])
    recommended = [book for _, book in scores[:top_n]]
    return recommended


def analyze_sentiment(text):
    sia = SentimentIntensityAnalyzer()
    score = sia.polarity_scores(text)
    return score['compound']  # от -1 до 1


def update_review_sentiments():
    reviews = Review.objects.filter(sentiment__isnull=True)
    for review in reviews:
        if review.text:
            sentiment_score = analyze_sentiment(review.text)
            ReviewSentiment.objects.update_or_create(review=review, defaults={'score': sentiment_score})


def embed_text(text):
    tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')
    model = AutoModel.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')

    inputs = tokenizer(text, return_tensors='pt', truncation=True, max_length=128)
    with torch.no_grad():
        outputs = model(**inputs)
    embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().cpu().numpy()
    return embeddings


def update_book_embeddings():
    for book in Book.objects.all():
        emb = embed_text(book.description or "")
        BookEmbedding.objects.update_or_create(book=book, defaults={'vector': emb.tolist()})


def update_review_embeddings():
    reviews = Review.objects.filter(reviewembedding__isnull=True).exclude(text__isnull=True).exclude(text__exact='')
    for review in reviews:
        emb = embed_text(review.text)
        ReviewEmbedding.objects.create(review=review, vector=emb.tolist())


def get_user_embedding(user):
    reviews = ReviewEmbedding.objects.filter(review__user=user)
    if not reviews.exists():
        return None
    embs = [np.array(r.vector) for r in reviews]
    return np.mean(embs, axis=0)


def recommend_books_by_embedding(user, top_n=10):
    user_emb = get_user_embedding(user)
    if user_emb is None:
        return Book.objects.none()

    all_embeddings = BookEmbedding.objects.select_related('book').all()
    scores = []
    for be in all_embeddings:
        dist = cosine(user_emb, np.array(be.vector))
        scores.append((dist, be.book))
    scores.sort(key=lambda x: x[0])
    recommended = [book for _, book in scores[:top_n]]
    return recommended
