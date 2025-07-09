from django.core.management.base import BaseCommand
from django.db import models
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity 

from books.models import Book, BookRating, UserBookRecommendation 
from django.core.management.base import BaseCommand

from books.recommendations.collaborative import run_collaborative_filtering
from books.recommendations.content_based import compute_and_store_tfidf_vectors_on_reviews, recommend_books_for_user_content
from books.recommendations.svd_model import train_and_save_svd_model, predict_svd 
from books.recommendations.torch_model import train_torch_model, predict_torch
from books.recommendations.word2_vec import compute_and_store_word2vec_vectors
from books.recommendations.node2vec_recommender import train_and_save_node2vec, predict_node2vec
from django.contrib.auth import get_user_model
User = get_user_model()



class Command(BaseCommand):
    help = 'Генерация модели'
    def handle(self, *args, **kwargs):
        self.stdout.write('Запуск collaborative filtering...')
        run_collaborative_filtering()
        self.stdout.write('Вычисление TF-IDF векторов...')
        compute_and_store_tfidf_vectors_on_reviews()
        self.stdout.write('Обучение и сохранение SVD модели...')
        train_and_save_svd_model()
        self.stdout.write('Обучение модели с помощью torch')
        train_torch_model()
        self.stdout.write('Вычисление и сохранение word2vec векторов...')
        compute_and_store_word2vec_vectors()
        self.stdout.write('Построение графа и обучение node2vec ')
        train_and_save_node2vec()
        self.stdout.write(self.style.SUCCESS('Все модели успешно сгенерированы.'))
