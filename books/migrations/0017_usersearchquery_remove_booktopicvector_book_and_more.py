# Generated by Django 4.2.19 on 2025-07-05 09:47

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('books', '0016_alter_bookrating_rating'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSearchQuery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=40, null=True)),
                ('query_text', models.CharField(max_length=255)),
                ('frequency', models.PositiveIntegerField(default=1)),
                ('last_searched', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='search_queries', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RemoveField(
            model_name='booktopicvector',
            name='book',
        ),
        migrations.RemoveField(
            model_name='reviewembedding',
            name='review',
        ),
        migrations.RemoveField(
            model_name='reviewsentiment',
            name='review',
        ),
        migrations.AddField(
            model_name='book',
            name='book_number_in_cycle',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='book',
            name='number_of_pages',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='book',
            name='year_of_publishing',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.DeleteModel(
            name='BookEmbedding',
        ),
        migrations.DeleteModel(
            name='BookTopicVector',
        ),
        migrations.DeleteModel(
            name='ReviewEmbedding',
        ),
        migrations.DeleteModel(
            name='ReviewSentiment',
        ),
        migrations.AddIndex(
            model_name='usersearchquery',
            index=models.Index(fields=['user', 'query_text'], name='books_users_user_id_4c94a4_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='usersearchquery',
            unique_together={('user', 'query_text')},
        ),
    ]
