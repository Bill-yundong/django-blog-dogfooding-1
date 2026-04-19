from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django_blog_it.models import Category, Tag, Article, Comment, Like, Favorite
from django.utils.text import slugify
from datetime import datetime, timedelta
import json


User = get_user_model()


class BaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        self.category = Category.objects.create(
            name='TestCategory',
            description='Test category',
            is_active=True,
            created_by=self.user
        )
        self.tag = Tag.objects.create(name='testtag')
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.article = Article.objects.create(
            title='Test Article for Sync',
            slug=slugify(f'test-article-sync-{timestamp}'),
            content='<p>Test content for article sync testing.</p>',
            category=self.category,
            status='Published',
            publish_on=datetime.now().date(),
            created_by=self.user,
            views=100,
            likes_count=0,
            comments_count=0
        )
        self.article.tags.add(self.tag)
        
        self.client = Client()


class CacheControlHeadersTestCase(BaseTestCase):
    """Test cache control headers for data sync fix"""
    
    def test_home_view_has_cache_control_headers(self):
        """Test that home view response includes no-cache headers"""
        response = self.client.get('/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-cache, no-store, must-revalidate')
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertEqual(response['Expires'], '0')
    
    def test_article_detail_view_has_cache_control_headers(self):
        """Test that article detail view response includes no-cache headers"""
        response = self.client.get(f'/article/{self.article.slug}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-cache, no-store, must-revalidate')
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertEqual(response['Expires'], '0')


class ArticleStatsAPITestCase(BaseTestCase):
    """Test the articles stats API for data sync"""
    
    def test_get_articles_stats_api_returns_correct_data(self):
        """Test that stats API returns correct article statistics"""
        response = self.client.get(f'/api/articles/stats/?slugs={self.article.slug}')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-cache, no-store, must-revalidate')
        
        data = json.loads(response.content)
        self.assertIn('articles', data)
        self.assertEqual(len(data['articles']), 1)
        
        article_data = data['articles'][0]
        self.assertEqual(article_data['slug'], self.article.slug)
        self.assertEqual(article_data['views'], 100)
        self.assertEqual(article_data['likes_count'], 0)
        self.assertEqual(article_data['comments_count'], 0)
    
    def test_get_articles_stats_api_multiple_articles(self):
        """Test that stats API handles multiple articles"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        article2 = Article.objects.create(
            title='Second Test Article',
            slug=slugify(f'second-test-article-{timestamp}'),
            content='<p>Second test content.</p>',
            category=self.category,
            status='Published',
            publish_on=datetime.now().date(),
            created_by=self.user,
            views=200,
            likes_count=5,
            comments_count=3
        )
        
        slugs = f'{self.article.slug},{article2.slug}'
        response = self.client.get(f'/api/articles/stats/?slugs={slugs}')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['articles']), 2)
    
    def test_get_articles_stats_api_empty_request(self):
        """Test that stats API handles empty request"""
        response = self.client.get('/api/articles/stats/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-cache, no-store, must-revalidate')
        
        data = json.loads(response.content)
        self.assertEqual(data['articles'], [])


class LikeSyncTestCase(BaseTestCase):
    """Test like count synchronization"""
    
    def test_like_count_updates_correctly(self):
        """Test that like count is updated after toggle like"""
        self.client.login(username='testuser', password='testpass123')
        
        initial_likes = self.article.likes_count
        
        response = self.client.post(
            '/like/',
            {'article_id': self.article.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(data['liked'])
        self.assertEqual(data['likes_count'], initial_likes + 1)
        
        self.article.refresh_from_db()
        self.assertEqual(self.article.likes_count, initial_likes + 1)
    
    def test_unlike_count_updates_correctly(self):
        """Test that like count decreases after unliking"""
        self.client.login(username='testuser', password='testpass123')
        
        Like.objects.create(user=self.user, article=self.article)
        self.article.likes_count = 1
        self.article.save()
        
        response = self.client.post(
            '/like/',
            {'article_id': self.article.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertFalse(data['liked'])
        self.assertEqual(data['likes_count'], 0)
        
        self.article.refresh_from_db()
        self.assertEqual(self.article.likes_count, 0)
    
    def test_like_response_has_cache_control_headers(self):
        """Test that like toggle response includes no-cache headers"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(
            '/like/',
            {'article_id': self.article.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response['Cache-Control'], 'no-cache, no-store, must-revalidate')
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertEqual(response['Expires'], '0')


class CommentSyncTestCase(BaseTestCase):
    """Test comment count synchronization"""
    
    def test_comment_count_updates_correctly(self):
        """Test that comment count is updated after adding comment"""
        self.client.login(username='testuser', password='testpass123')
        
        initial_comments = self.article.comments_count
        
        response = self.client.post(
            f'/article/{self.article.slug}/comment/',
            {'content': 'Test comment for sync'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, initial_comments + 1)
    
    def test_comment_delete_updates_count(self):
        """Test that comment count decreases after deletion"""
        self.client.login(username='testuser', password='testpass123')
        
        comment = Comment.objects.create(
            article=self.article,
            user=self.user,
            content='Test comment to delete'
        )
        self.article.comments_count = 1
        self.article.save()
        
        response = self.client.post(
            f'/comment/{comment.id}/delete/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 0)


class ViewCountSyncTestCase(BaseTestCase):
    """Test view count synchronization"""
    
    def test_view_count_increases_on_article_visit(self):
        """Test that view count increases when visiting article detail"""
        initial_views = self.article.views
        
        response = self.client.get(f'/article/{self.article.slug}/')
        
        self.assertEqual(response.status_code, 200)
        
        self.article.refresh_from_db()
        self.assertEqual(self.article.views, initial_views + 1)
    
    def test_stats_api_reflects_updated_view_count(self):
        """Test that stats API returns updated view count"""
        initial_views = self.article.views
        
        self.client.get(f'/article/{self.article.slug}/')
        
        response = self.client.get(f'/api/articles/stats/?slugs={self.article.slug}')
        data = json.loads(response.content)
        
        article_data = data['articles'][0]
        self.assertEqual(article_data['views'], initial_views + 1)


class FavoriteSyncTestCase(BaseTestCase):
    """Test favorite count synchronization"""
    
    def test_favorite_count_updates_correctly(self):
        """Test that favorite count is updated after toggle favorite"""
        self.client.login(username='testuser', password='testpass123')
        
        initial_favorites = self.article.favorites_count
        
        response = self.client.post(
            f'/article/{self.article.slug}/favorite/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(data['favorited'])
        self.assertEqual(data['favorites_count'], initial_favorites + 1)
        
        self.article.refresh_from_db()
        self.assertEqual(self.article.favorites_count, initial_favorites + 1)
    
    def test_favorite_response_has_cache_control_headers(self):
        """Test that favorite toggle response includes no-cache headers"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(
            f'/article/{self.article.slug}/favorite/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response['Cache-Control'], 'no-cache, no-store, must-revalidate')
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertEqual(response['Expires'], '0')


class DataSyncIntegrationTestCase(BaseTestCase):
    """Integration tests for complete data sync workflow"""
    
    def test_complete_sync_workflow(self):
        """Test complete workflow: view article -> like -> comment -> check stats"""
        self.client.login(username='testuser', password='testpass123')
        
        self.client.get(f'/article/{self.article.slug}/')
        self.article.refresh_from_db()
        views_after_visit = self.article.views
        
        self.client.post(
            '/like/',
            {'article_id': self.article.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.article.refresh_from_db()
        likes_after_toggle = self.article.likes_count
        
        self.client.post(
            f'/article/{self.article.slug}/comment/',
            {'content': 'Integration test comment'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.article.refresh_from_db()
        comments_after_add = self.article.comments_count
        
        response = self.client.get(f'/api/articles/stats/?slugs={self.article.slug}')
        data = json.loads(response.content)
        article_data = data['articles'][0]
        
        self.assertEqual(article_data['views'], views_after_visit)
        self.assertEqual(article_data['likes_count'], likes_after_toggle)
        self.assertEqual(article_data['comments_count'], comments_after_add)
    
    def test_home_page_displays_updated_stats(self):
        """Test that home page displays updated statistics"""
        self.article.views = 500
        self.article.likes_count = 25
        self.article.comments_count = 10
        self.article.save()
        
        response = self.client.get('/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '500')
        self.assertContains(response, '25')
        self.assertContains(response, '10')
