from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.db import connection
from .models import Article, Category, Tag, Comment, Like, Favorite, UserProfile, Follow

User = get_user_model()


class CacheControlTestCase(TestCase):
    """测试缓存控制修复 - 验证首页返回正确的缓存控制头"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Test Category',
            description='Test Description',
            created_by=self.user
        )
        self.article = Article.objects.create(
            title='Test Article',
            slug='test-article',
            content='<p>Test content</p>',
            category=self.category,
            status='Published',
            created_by=self.user,
            views=100,
            likes_count=10,
            comments_count=5
        )
    
    def test_home_page_cache_control_headers(self):
        """验证首页响应包含正确的缓存控制头"""
        response = self.client.get(reverse('django_blog_it:home'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-cache, no-store, must-revalidate')
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertEqual(response['Expires'], '0')
    
    def test_home_page_refreshes_article_data(self):
        """验证首页显示最新的文章数据"""
        # 首次访问首页
        response1 = self.client.get(reverse('django_blog_it:home'))
        self.assertEqual(response1.status_code, 200)
        self.assertContains(response1, '100')  # 初始阅读数
        
        # 模拟文章被访问，更新阅读数
        self.article.refresh_from_db()
        self.article.views = 150
        self.article.likes_count = 20
        self.article.comments_count = 8
        self.article.save()
        
        # 再次访问首页，应显示更新后的数据
        response2 = self.client.get(reverse('django_blog_it:home'))
        self.assertEqual(response2.status_code, 200)
        self.assertContains(response2, '150')  # 更新后的阅读数


class ArticleDetailTestCase(TestCase):
    """测试文章详情页功能"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Tech',
            description='Technology',
            created_by=self.user
        )
        self.article = Article.objects.create(
            title='Django Testing Guide',
            slug='django-testing-guide',
            content='<h1>Django Testing</h1><p>Learn to test Django apps</p>',
            category=self.category,
            status='Published',
            created_by=self.user,
            views=50,
            likes_count=5,
            comments_count=2
        )
    
    def test_article_detail_increases_views(self):
        """验证访问文章详情页会增加阅读数"""
        initial_views = self.article.views
        
        response = self.client.get(
            reverse('django_blog_it:article_detail', kwargs={'slug': self.article.slug})
        )
        
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.views, initial_views + 1)
    
    def test_article_detail_displays_correct_data(self):
        """验证文章详情页显示正确的数据"""
        response = self.client.get(
            reverse('django_blog_it:article_detail', kwargs={'slug': self.article.slug})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)
        self.assertContains(response, self.article.content)
        self.assertContains(response, self.article.category.name)
    
    def test_article_detail_404_for_nonexistent_slug(self):
        """验证访问不存在的文章返回404"""
        response = self.client.get(
            reverse('django_blog_it:article_detail', kwargs={'slug': 'nonexistent-article'})
        )
        self.assertEqual(response.status_code, 404)


class LikeSystemTestCase(TestCase):
    """测试点赞系统功能"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Tech',
            description='Technology',
            created_by=self.user
        )
        self.article = Article.objects.create(
            title='Like Test Article',
            slug='like-test-article',
            content='<p>Test content</p>',
            category=self.category,
            status='Published',
            created_by=self.user,
            likes_count=0
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_toggle_like_adds_like(self):
        """验证点赞功能正常工作"""
        response = self.client.post(
            reverse('django_blog_it:toggle_like'),
            {'article_id': self.article.id}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['liked'])
        
        # 验证数据库
        self.article.refresh_from_db()
        self.assertEqual(self.article.likes_count, 1)
        self.assertTrue(
            Like.objects.filter(user=self.user, article=self.article).exists()
        )
    
    def test_toggle_like_removes_like(self):
        """验证再次点击取消点赞"""
        # 先点赞
        Like.objects.create(user=self.user, article=self.article)
        self.article.likes_count = 1
        self.article.save()
        
        # 再次点击取消
        response = self.client.post(
            reverse('django_blog_it:toggle_like'),
            {'article_id': self.article.id}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['liked'])
        
        # 验证数据库
        self.article.refresh_from_db()
        self.assertEqual(self.article.likes_count, 0)


class CommentSystemTestCase(TestCase):
    """测试评论系统功能"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Tech',
            description='Technology',
            created_by=self.user
        )
        self.article = Article.objects.create(
            title='Comment Test Article',
            slug='comment-test-article',
            content='<p>Test content</p>',
            category=self.category,
            status='Published',
            created_by=self.user,
            comments_count=0
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_add_comment(self):
        """验证添加评论功能"""
        response = self.client.post(
            reverse('django_blog_it:add_comment', kwargs={'slug': self.article.slug}),
            {'content': 'This is a test comment'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # 验证数据库
        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 1)
        self.assertEqual(
            Comment.objects.filter(article=self.article).count(),
            1
        )
    
    def test_delete_comment(self):
        """验证删除评论功能"""
        comment = Comment.objects.create(
            article=self.article,
            user=self.user,
            content='Test comment'
        )
        self.article.comments_count = 1
        self.article.save()
        
        response = self.client.post(
            reverse('django_blog_it:delete_comment', kwargs={'comment_id': comment.id})
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # 验证数据库
        self.article.refresh_from_db()
        self.assertEqual(self.article.comments_count, 0)


class SearchFunctionalityTestCase(TestCase):
    """测试搜索功能"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Python',
            description='Python Programming',
            created_by=self.user
        )
        self.article1 = Article.objects.create(
            title='Python Tutorial',
            slug='python-tutorial',
            content='<p>Learn Python programming</p>',
            category=self.category,
            status='Published',
            created_by=self.user
        )
        self.article2 = Article.objects.create(
            title='Django Guide',
            slug='django-guide',
            content='<p>Web development with Django</p>',
            category=self.category,
            status='Published',
            created_by=self.user
        )
    
    def test_search_by_query(self):
        """验证按关键词搜索"""
        response = self.client.get(
            reverse('django_blog_it:search'),
            {'q': 'Python'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Python Tutorial')
    
    def test_search_by_category(self):
        """验证按分类搜索"""
        response = self.client.get(
            reverse('django_blog_it:search'),
            {'category': self.category.id}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Python Tutorial')
        self.assertContains(response, 'Django Guide')


class UserProfileTestCase(TestCase):
    """测试用户资料功能"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.client.login(username='testuser', password='testpass123')
    
    def test_profile_page_accessible(self):
        """验证用户资料页可访问"""
        response = self.client.get(
            reverse('django_blog_it:user_profile', kwargs={'username': self.user.username})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.username)
    
    def test_edit_profile(self):
        """验证编辑用户资料"""
        response = self.client.post(
            reverse('django_blog_it:edit_profile'),
            {
                'bio': 'Test bio',
                'website': 'https://example.com',
                'location': 'Test City'
            }
        )
        
        self.assertEqual(response.status_code, 302)  # 重定向
        
        # 验证数据库
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, 'Test bio')
        self.assertEqual(self.profile.website, 'https://example.com')


class FollowSystemTestCase(TestCase):
    """测试关注系统功能"""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        self.client.login(username='user1', password='testpass123')
    
    def test_toggle_follow(self):
        """验证关注/取消关注功能"""
        response = self.client.post(
            reverse('django_blog_it:toggle_follow', kwargs={'username': self.user2.username})
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['following'])
        
        # 验证数据库
        self.assertTrue(
            Follow.objects.filter(follower=self.user1, following=self.user2).exists()
        )
    
    def test_cannot_follow_self(self):
        """验证不能关注自己"""
        response = self.client.post(
            reverse('django_blog_it:toggle_follow', kwargs={'username': self.user1.username})
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])


class NavigationFlowTestCase(TestCase):
    """测试导航流程 - 模拟用户从首页到详情页再返回"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Tech',
            description='Technology',
            created_by=self.user
        )
        self.article = Article.objects.create(
            title='Flow Test Article',
            slug='flow-test-article',
            content='<p>Test content for flow</p>',
            category=self.category,
            status='Published',
            created_by=self.user,
            views=10,
            likes_count=3,
            comments_count=1
        )
        Comment.objects.create(
            article=self.article,
            user=self.user,
            content='Test comment',
            is_active=True
        )
    
    def test_home_to_detail_back_to_home_flow(self):
        """模拟用户从首页进入详情页再返回首页的完整流程"""
        # 1. 访问首页
        home_response = self.client.get(reverse('django_blog_it:home'))
        self.assertEqual(home_response.status_code, 200)
        initial_views = self.article.views
        
        # 验证首页显示正确数据
        self.assertContains(home_response, self.article.title)
        self.assertContains(home_response, str(initial_views))
        
        # 2. 进入文章详情页
        detail_response = self.client.get(
            reverse('django_blog_it:article_detail', kwargs={'slug': self.article.slug})
        )
        self.assertEqual(detail_response.status_code, 200)
        
        # 验证阅读数增加
        self.article.refresh_from_db()
        self.assertEqual(self.article.views, initial_views + 1)
        
        # 3. 返回首页
        home_response2 = self.client.get(reverse('django_blog_it:home'))
        self.assertEqual(home_response2.status_code, 200)
        
        # 验证首页显示更新后的数据
        self.assertContains(home_response2, str(self.article.views))
        
        # 4. 验证缓存控制头确保数据新鲜
        self.assertEqual(home_response2['Cache-Control'], 'no-cache, no-store, must-revalidate')


class ModelIntegrityTestCase(TestCase):
    """测试模型数据完整性"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_article_slug_uniqueness(self):
        """验证文章slug唯一性"""
        category = Category.objects.create(
            name='Test',
            created_by=self.user
        )
        
        Article.objects.create(
            title='Test Article',
            slug='unique-slug',
            content='Content',
            category=category,
            status='Published',
            created_by=self.user
        )
        
        # 尝试创建相同slug的文章应该失败
        with self.assertRaises(Exception):
            Article.objects.create(
                title='Another Article',
                slug='unique-slug',
                content='Content',
                category=category,
                status='Published',
                created_by=self.user
            )
    
    def test_category_auto_slug(self):
        """验证分类自动生成slug"""
        category = Category.objects.create(
            name='Test Category',
            created_by=self.user
        )
        self.assertEqual(category.slug, 'test-category')
