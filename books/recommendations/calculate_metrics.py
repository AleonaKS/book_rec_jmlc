import sys
import os
 
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
 
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "books_site.settings")
django.setup()

import numpy as np
from collections import defaultdict
from books.models import Review, User, Book, BookVector

from .collaborative import get_similar_books_item_based, get_recommendations_for_user_user_based
from .content_based import get_similar_books_content, recommend_books_for_user_content, get_similar_books_combined
from .svd_model import get_svd_recommendations_for_user 
from .word2_vec import get_similar_books_by_w2v
from .node2vec_recommender import recommend_books_node2vec
from .torch_model import predict_torch
from .hybrid import hybrid_recommendations_for_user, hybrid_recommendations_for_book
from django.db import models
 

import csv
import math 
from statistics import mean
from itertools import combinations

# Метрики

def f1_score(precision, recall):
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)

def average_precision(relevant_items, recommended_items):
    hits = 0
    sum_precisions = 0.0
    for i, item in enumerate(recommended_items, start=1):
        if item in relevant_items:
            hits += 1
            sum_precisions += hits / i
    if hits == 0:
        return 0.0
    return sum_precisions / hits

def dcg(relevant_items, recommended_items, k=None):
    dcg_value = 0.0
    for i, item in enumerate(recommended_items[:k], start=1):
        rel = 1 if item in relevant_items else 0
        dcg_value += (2 ** rel - 1) / math.log2(i + 1)
    return dcg_value

def idcg(relevant_items, k=None):
    ideal_rels = [1] * min(len(relevant_items), k if k else len(relevant_items))
    idcg_value = 0.0
    for i, rel in enumerate(ideal_rels, start=1):
        idcg_value += (2 ** rel - 1) / math.log2(i + 1)
    return idcg_value

def ndcg(relevant_items, recommended_items, k=None):
    idcg_value = idcg(relevant_items, k)
    if idcg_value == 0:
        return 0.0
    return dcg(relevant_items, recommended_items, k) / idcg_value

def reciprocal_rank(relevant_items, recommended_items):
    for i, item in enumerate(recommended_items, start=1):
        if item in relevant_items:
            return 1 / i
    return 0.0

# Coverage и Diversity

def coverage(all_recommended_items, all_items):
    unique_recommended = set(all_recommended_items)
    return len(unique_recommended) / len(all_items) if all_items else 0


def distance(book1_id, book2_id):
    try:
        vec1 = np.array(BookVector.objects.get(book_id=book1_id).w2v_vector)
        vec2 = np.array(BookVector.objects.get(book_id=book2_id).w2v_vector)
    except BookVector.DoesNotExist:
        # Если вектора нет, считаем максимальное расстояние (например, 1)
        return 1.0

    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 1.0

    cosine_sim = np.dot(vec1, vec2) / (norm1 * norm2)
    return 1 - cosine_sim


def diversity(recommended_items):
    if len(recommended_items) < 2:
        return 0.0
    distances = []
    for b1, b2 in combinations(recommended_items, 2):
        distances.append(distance(b1, b2))
    return sum(distances) / len(distances)
 

def get_recommendations_all_methods(user, TOP_N=10):
    recs = {}

    svd_books = get_svd_recommendations_for_user(user.id, top_n=TOP_N)
    svd_list = [b.id for b in svd_books]
    recs['svd'] = {'set': set(svd_list), 'list': svd_list}

    node2vec_df = recommend_books_node2vec(user.id, top_n=TOP_N)
    node2vec_list = node2vec_df['book_id'].tolist()
    recs['node2vec'] = {'set': set(node2vec_list), 'list': node2vec_list}

    all_book_ids = list(Book.objects.values_list('id', flat=True))
    preds = predict_torch(user.id, all_book_ids)
    sorted_preds = sorted(preds.items(), key=lambda x: x[1], reverse=True)[:TOP_N]
    torch_list = [bid for bid, score in sorted_preds]
    recs['torch'] = {'set': set(torch_list), 'list': torch_list}

    hybrid_books = hybrid_recommendations_for_user(user, top_n=TOP_N)
    hybrid_list = [b.id for b in hybrid_books]
    recs['hybrid'] = {'set': set(hybrid_list), 'list': hybrid_list}

    content_books = recommend_books_for_user_content(user, top_n=TOP_N)
    content_list = [b.id for b in content_books]
    recs['content'] = {'set': set(content_list), 'list': content_list}

    collab_books = get_recommendations_for_user_user_based(user.id, top_n=TOP_N)
    collab_list = [b.id for b in collab_books]
    recs['collaborative'] = {'set': set(collab_list), 'list': collab_list}

    read_books = get_read_books_for_user(user.id)
    if read_books:
        w2v_recs = get_similar_books_by_w2v(next(iter(read_books)), top_n=TOP_N)
        w2v_list = [rec['book'].id for rec in w2v_recs]
    else:
        w2v_list = []
    recs['word2vec'] = {'set': set(w2v_list), 'list': w2v_list}

    return recs



def get_relevant_books(user_id, rating_threshold=4):
    relevant = Review.objects.filter(user_id=user_id, rating__gte=rating_threshold).values_list('book_id', flat=True)
    return set(relevant)

def recall_at_k(recommended_books, relevant_books, k):
    recommended_top = list(recommended_books)[:k]
    hits = len(set(recommended_top).intersection(relevant_books))
    if not relevant_books:
        return 0.0
    return hits / len(relevant_books)

def precision_at_k(recommended_books, relevant_books, k):
    recommended_top = list(recommended_books)[:k]
    hits = len(set(recommended_top).intersection(relevant_books))
    if k == 0:
        return 0.0
    return hits / k




def calculate_metrics_for_users_extended(TOP_N_list=[10,20,30,40], year=2025, min_reads=2, rating_threshold=4, csv_path='metrics_results.csv'):
    users_ids = (
        Review.objects.filter(review_date__year=year)
        .values('user')
        .annotate(count=models.Count('book', distinct=True))
        .filter(count__gte=min_reads)
        .values_list('user', flat=True)
    )
    print(f"Найдено пользователей с минимум {min_reads} прочитанными книгами в {year}: {len(users_ids)}")

    all_books = set(Book.objects.values_list('id', flat=True))

    # Для coverage считаем глобально по всем рекомендациям и всем TOP_N
    coverage_per_method_per_k = {k: defaultdict(set) for k in TOP_N_list}

    # Словари для хранения метрик: {TOP_N: {method: [значения по пользователям]}}
    metrics = {k: defaultdict(lambda: defaultdict(list)) for k in TOP_N_list}
    # ключи метрик: recall, precision, f1, map, ndcg, mrr, diversity

    for user_id in users_ids:
        user = User.objects.get(id=user_id)
        read_books = get_read_books_for_user(user_id, year=year)
        if not read_books:
            continue

        relevant = get_relevant_books(user_id, rating_threshold)
        if not relevant:
            continue

        recs_all = get_recommendations_all_methods(user, TOP_N=max(TOP_N_list))

        for k in TOP_N_list:
            for method, recs_dict in recs_all.items():
                rec_set = recs_dict['set']
                rec_list = recs_dict['list'][:k]

                # Обновляем coverage
                coverage_per_method_per_k[k][method].update(rec_list)

                # Метрики
                r = recall_at_k(rec_set, relevant, k)
                p = precision_at_k(rec_set, relevant, k)
                f1 = f1_score(p, r)
                ap = average_precision(relevant, rec_list)
                n = ndcg(relevant, rec_list, k)
                mrr = reciprocal_rank(relevant, rec_list)
                div = diversity(rec_list)

                metrics[k][method]['recall'].append(r)
                metrics[k][method]['precision'].append(p)
                metrics[k][method]['f1'].append(f1)
                metrics[k][method]['map'].append(ap)
                metrics[k][method]['ndcg'].append(n)
                metrics[k][method]['mrr'].append(mrr)
                metrics[k][method]['diversity'].append(div)

    # Подсчёт средних и coverage
    summary = {}
    for k in TOP_N_list:
        summary[k] = {}
        for method in metrics[k]:
            summary[k][method] = {}
            for metric_name, vals in metrics[k][method].items():
                summary[k][method][metric_name] = mean(vals) if vals else 0.0
            # coverage для метода и k
            summary[k][method]['coverage'] = coverage(coverage_per_method_per_k[k][method], all_books)

    # запись в csv
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        header = ['TOP_N', 'Method', 'Recall', 'Precision', 'F1', 'MAP', 'NDCG', 'MRR', 'Coverage', 'Diversity']
        writer.writerow(header)
        for k in TOP_N_list:
            for method, met_dict in summary[k].items():
                writer.writerow([
                    k,
                    method,
                    f"{met_dict.get('recall',0):.4f}",
                    f"{met_dict.get('precision',0):.4f}",
                    f"{met_dict.get('f1',0):.4f}",
                    f"{met_dict.get('map',0):.4f}",
                    f"{met_dict.get('ndcg',0):.4f}",
                    f"{met_dict.get('mrr',0):.4f}",
                    f"{met_dict.get('coverage',0):.4f}",
                    f"{met_dict.get('diversity',0):.4f}",
                ])

    print(f"Метрики посчитаны и сохранены в {csv_path}")
    return summary

def get_read_books_for_user(user_id, year=2025):
    book_ids = (
        Review.objects.filter(user_id=user_id, review_date__year=year)
        .values_list('book_id', flat=True)
        .distinct()
    )
    return set(book_ids)




# ===== from books.models import User, Review, Book
# from recommendations.svd_model import get_svd_recommendations_for_user
# from recommendations.torch_model import recommend_books_for_user_simple
# from recommendations.node2vec_recommender import recommend_books_node2vec
# from recommendations.calculate_metrics import (
#     recall_at_k, precision_at_k, f1_score, average_precision, ndcg, reciprocal_rank, diversity
# )

# def get_relevant_books(user_id, rating_threshold=4):
#     relevant = Review.objects.filter(user_id=user_id, rating__gte=rating_threshold).values_list('book_id', flat=True)
#     return set(relevant)

# def calculate_metrics_for_model(model_name, user_ids, top_n=10, rating_threshold=4):
#     metrics_accum = {
#         'recall': [],
#         'precision': [],
#         'f1': [],
#         'map': [],
#         'ndcg': [],
#         'mrr': [],
#         'diversity': []
#     }

#     for user_id in user_ids:
#         user = User.objects.get(id=user_id)
#         relevant = get_relevant_books(user_id, rating_threshold)
#         if not relevant:
#             continue

#         # Получаем рекомендации по модели
#         if model_name == 'svd':
#             rec_books = get_svd_recommendations_for_user(user.id, top_n=top_n)
#             rec_list = [b.id for b in rec_books]
#         elif model_name == 'torch':
#             rec_books = recommend_books_for_user_simple(user.id, top_n=top_n)
#             rec_list = [b.id for b in rec_books]
#         elif model_name == 'node2vec':
#             df = recommend_books_node2vec(user.id, top_n=top_n)
#             rec_list = df['book_id'].tolist()
#         else:
#             raise ValueError(f"Unknown model name: {model_name}")

#         rec_set = set(rec_list)

#         r = recall_at_k(rec_set, relevant, top_n)
#         p = precision_at_k(rec_set, relevant, top_n)
#         f1 = f1_score(p, r)
#         ap = average_precision(relevant, rec_list)
#         n = ndcg(relevant, rec_list, top_n)
#         mrr = reciprocal_rank(relevant, rec_list)
#         div = diversity(rec_list)

#         metrics_accum['recall'].append(r)
#         metrics_accum['precision'].append(p)
#         metrics_accum['f1'].append(f1)
#         metrics_accum['map'].append(ap)
#         metrics_accum['ndcg'].append(n)
#         metrics_accum['mrr'].append(mrr)
#         metrics_accum['diversity'].append(div)

#     # Средние по всем пользователям
#     from statistics import mean
#     summary = {metric: mean(vals) if vals else 0.0 for metric, vals in metrics_accum.items()}
#     return summary

# # Пример вызова
# if __name__ == '__main__':
#     # Получаем пользователей с минимум 2 прочитанными книгами за 2025 год
#     users_ids = (
#         Review.objects.filter(review_date__year=2025)
#         .values('user')
#         .annotate(count=models.Count('book', distinct=True))
#         .filter(count__gte=2)
#         .values_list('user', flat=True)
#     )

#     top_n = 10
#     for model in ['svd', 'torch', 'node2vec']:
#         print(f"Метрики для модели {model}:")
#         summary = calculate_metrics_for_model(model, users_ids, top_n=top_n)
#         for metric, val in summary.items():
#             print(f"  {metric}: {val:.4f}")
#         print()
