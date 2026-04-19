from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django_blog_it.models import Article, Category, Like, Comment
from django.utils.text import slugify
from datetime import datetime, timedelta


class ArticleStatsSyncTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.admin_user = User.objects.create_user(
            username='testadmin',
            email='test@example.com',
            password='test123',
            is_superuser=True,
            is_staff=True
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            description='Test',
            is_active=True,
            created_by=self.admin_user
        )
        
        self.article = Article.objects.create(
            title='Test Article for Sync',
            slug=slugify('test-article-sync'),
            content='Test content',
            category=self.category,
            status='Published',
            publish_on=datetime.now().date(),
            created_by=self.admin_user,
            views=100,
            likes_count=10,
            comments_count=5
        )

    def test_article_stats_api_exists(self):
        """测试文章统计API接口存在且返回正确数据"""
        response = self.client.get(reverse('django_blog_it:get_article_stats'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        self.assertIn('stats', data)
        self.assertIn(str(self.article.id), data['stats'])
        
        stats = data['stats'][str(self.article.id)]
        self.assertEqual(stats['views'], 100)
        self.assertEqual(stats['likes_count'], 10)
        self.assertEqual(stats['comments_count'], 5)

    def test_article_stats_api_cache_headers(self):
        """测试统计API正确设置缓存控制头"""
        response = self.client.get(reverse('django_blog_it:get_article_stats'))
        self.assertIn('no-cache', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('must-revalidate', response['Cache-Control'])

    def test_home_page_cache_headers(self):
        """测试首页正确设置缓存控制头"""
        response = self.client.get(reverse('django_blog_it:home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-cache', response['Cache-Control'])
        self.assertIn('no-store', response['Cache-Control'])

    def test_home_page_contains_article_ids(self):
        """测试首页文章卡片包含正确的data-article-id属性"""
        response = self.client.get(reverse('django_blog_it:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-article-id')
        self.assertContains(response, str(self.article.id))

    def test_like_updates_article_stats(self):
        """测试点赞后文章统计数据正确更新"""
        self.client.login(username='testadmin', password='test123')
        
        self.assertEqual(self.article.likes.count(), 0)
        
        response = self.client.post(reverse('django_blog_it:toggle_like'), {
            'article_id': self.article.id
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        
        self.article.refresh_from_db()
        self.assertEqual(self.article.likes.count(), 1)
        self.assertEqual(self.article.likes_count, 1)

    def test_view_increase_on_article_detail(self):
        """测试访问文章详情页阅读数自动增加"""
        initial_views = self.article.views
        
        response = self.client.get(reverse('django_blog_it:article_detail', kwargs={
            'slug': self.article.slug
        }))
        self.assertEqual(response.status_code, 200)
        
        self.article.refresh_from_db()
        self.assertEqual(self.article.views, initial_views + 1)

    def test_home_page_javascript_injection(self):
        """测试首页包含数据同步JavaScript代码"""
        response = self.client.get(reverse('django_blog_it:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'updateArticleStats')
        self.assertContains(response, 'localStorage')
        self.assertContains(response, 'visibilitychange')
        self.assertContains(response, 'pageshow')
        self.assertContains(response, 'setInterval')

    def test_article_detail_broadcast_function(self):
        """测试文章详情页包含广播更新函数"""
        response = self.client.get(reverse('django_blog_it:article_detail', kwargs={
            'slug': self.article.slug
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'broadcastArticleUpdate')
        self.assertContains(response, 'article_stats_updated')
