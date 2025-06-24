import os
import django
import logging
from datetime import datetime
from collections import defaultdict, Counter

 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'books_site.settings')
django.setup()
 
from books.models import Book, Review, BookRating, UserBookStatus, UserSubscription, UserPreferences, FavoriteAuthors, FavoriteGenres, FavoriteTags, DislikedGenres, DislikedTags
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  

from django.contrib.auth.models import User

MIN_REVIEWS_COUNT = 3   

def update_user_preferences_from_reviews(user): 
    reviews_count = Review.objects.filter(user=user).count()
    ratings_count = BookRating.objects.filter(user=user).count()
    total_count = reviews_count + ratings_count
 
    if total_count < MIN_REVIEWS_COUNT:
        return
 
    reviews = Review.objects.filter(user=user)
    ratings = BookRating.objects.filter(user=user)

    author_scores = defaultdict(list)   
    genre_scores = defaultdict(list)   
    tag_scores = defaultdict(list)     
 
    def add_scores(book, rating):
        if rating is None:
            return
        for author in book.author.all():
            author_scores[author.id].append(rating)
        if book.genre:
            genre_scores[book.genre.id].append(rating)
        for tag in book.tags.all():
            tag_scores[tag.id].append(rating)
 
    for review in reviews:
        add_scores(review.book, review.rating)
 
    for br in ratings:
        add_scores(br.book, br.rating)
 
    profile, _ = UserPreferences.objects.get_or_create(user=user)
 
    for author_id, scores in author_scores.items():
        if len(scores) < MIN_REVIEWS_COUNT:
            continue
        avg_score = sum(scores) / len(scores)
        fav_author, created = FavoriteAuthors.objects.get_or_create(
            userprofile=profile,
            author_id=author_id,
            defaults={'score': avg_score}
        )
        if not created:
            fav_author.score = avg_score
            fav_author.save(update_fields=['score'])
 
    for genre_id, scores in genre_scores.items():
        if len(scores) < MIN_REVIEWS_COUNT:
            FavoriteGenres.objects.filter(userprofile=profile, genre_id=genre_id).delete()
            DislikedGenres.objects.filter(userprofile=profile, genre_id=genre_id).delete()
            continue
        avg_score = sum(scores) / len(scores)
        if avg_score >= 4.0:
            fav_genre, created = FavoriteGenres.objects.get_or_create(
                userprofile=profile,
                genre_id=genre_id,
                defaults={'score': avg_score}
            )
            if not created:
                fav_genre.score = avg_score
                fav_genre.save(update_fields=['score'])
            DislikedGenres.objects.filter(userprofile=profile, genre_id=genre_id).delete()
        elif avg_score <= 2.0:
            disliked_genre, created = DislikedGenres.objects.get_or_create(
                userprofile=profile,
                genre_id=genre_id,
                defaults={'score': avg_score}
            )
            if not created:
                disliked_genre.score = avg_score
                disliked_genre.save(update_fields=['score'])
            FavoriteGenres.objects.filter(userprofile=profile, genre_id=genre_id).delete()
        else:
            FavoriteGenres.objects.filter(userprofile=profile, genre_id=genre_id).delete()
            DislikedGenres.objects.filter(userprofile=profile, genre_id=genre_id).delete()
 
    for tag_id, scores in tag_scores.items():
        if len(scores) < MIN_REVIEWS_COUNT:
            FavoriteTags.objects.filter(userprofile=profile, tag_id=tag_id).delete()
            DislikedTags.objects.filter(userprofile=profile, tag_id=tag_id).delete()
            continue
        avg_score = sum(scores) / len(scores)
        if avg_score >= 3.5:
            fav_tag, created = FavoriteTags.objects.get_or_create(
                userprofile=profile,
                tag_id=tag_id,
                defaults={'score': avg_score}
            )
            if not created:
                fav_tag.score = avg_score
                fav_tag.save(update_fields=['score'])
            DislikedTags.objects.filter(userprofile=profile, tag_id=tag_id).delete()
        elif avg_score <= 2.5:
            disliked_tag, created = DislikedTags.objects.get_or_create(
                userprofile=profile,
                tag_id=tag_id,
                defaults={'score': avg_score}
            )
            if not created:
                disliked_tag.score = avg_score
                disliked_tag.save(update_fields=['score'])
            FavoriteTags.objects.filter(userprofile=profile, tag_id=tag_id).delete()
        else:
            FavoriteTags.objects.filter(userprofile=profile, tag_id=tag_id).delete()
            DislikedTags.objects.filter(userprofile=profile, tag_id=tag_id).delete()

# 
def update_user_bookstatus():
    for review in Review.objects.select_related('user', 'book').all():
        UserBookStatus.objects.get_or_create(
            user=review.user,
            book=review.book,
            status=UserBookStatus.STATUS_PURCHASED,
            defaults={'added_at': review.review_date or datetime.now()}
        )


def update_user_subscription(user):
    purchased_books = Book.objects.filter(
        userbookstatus__user=user,
        userbookstatus__status=UserBookStatus.STATUS_PURCHASED
    ).select_related('cycle').prefetch_related('author') 
    author_counter = Counter()
    for book in purchased_books:
        for author in book.author.all():
            author_counter[author] += 1
    for author, count in author_counter.items():
        if count >= 5:
            UserSubscription.objects.get_or_create(
                user=user,
                content_type='AUTHOR',
                author=author
            ) 
    cycle_counter = Counter(book.cycle for book in purchased_books if book.cycle)
    for cycle, count in cycle_counter.items():
        if count >= 2:
            UserSubscription.objects.get_or_create(
                user=user,
                content_type='CYCLE',
                cycle=cycle
            )

def main():
    for user in User.objects.all():
        update_user_preferences_from_reviews(user)
        update_user_subscription(user)
    update_user_bookstatus()

if __name__ == '__main__':
    main()
