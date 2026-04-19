import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blog_test.settings')
django.setup()

from django.contrib.auth import get_user_model
from django_blog_it.models import Category, Tag, Article
from django.utils.text import slugify
from datetime import datetime, timedelta

User = get_user_model()

admin_user, created = User.objects.get_or_create(
    username='admin',
    defaults={
        'email': 'admin@example.com',
        'is_superuser': True,
        'is_staff': True,
        'is_active': True,
    }
)
if created:
    admin_user.set_password('admin123')
    admin_user.save()

print('admin用户:', admin_user)

if Category.objects.count() == 0:
    print('开始创建分类和文章...')
    tags_data = ['Python', 'Django', 'JavaScript', 'Vue', 'React', 'Database', 'Frontend', 'Backend', 'DevOps', 'AI']
    tags = []
    for tag_name in tags_data:
        tag, _ = Tag.objects.get_or_create(name=tag_name)
        tags.append(tag)
    print('创建了标签:', len(tags))
    
    cat1, _ = Category.objects.get_or_create(
        name='Tech',
        defaults={
            'description': 'Technology articles',
            'is_active': True,
            'created_by': admin_user,
        }
    )
    cat2, _ = Category.objects.get_or_create(
        name='Life',
        defaults={
            'description': 'Life articles',
            'is_active': True,
            'created_by': admin_user,
        }
    )
    categories = [cat1, cat2]
    print('创建分类成功')
    
    base_titles = [
        'Introduction to Django Framework',
        'Python Programming Best Practices',
        'Getting Started with Vue.js 3',
        'Database Optimization Techniques',
        'My Journey as a Developer',
        'Building REST APIs with Django',
        'JavaScript ES6+ Features',
        'Docker for Developers',
        'Machine Learning Basics',
        'Web Security Essentials',
        'CSS Grid Layout Guide',
        'Git Workflow Tips'
    ]
    
    for i, base_title in enumerate(base_titles):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        slug = slugify(f'{base_title}-{timestamp}-{i}')
        
        Article.objects.create(
            title=base_title,
            slug=slug,
            content=f'<h2>{base_title}</h2><p>This is a comprehensive sample article about {base_title.lower()}.</p><p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>',
            category=categories[0] if i < 8 else categories[1],
            status='Published',
            publish_on=datetime.now().date() - timedelta(days=i),
            created_by=admin_user,
            views=100 + i * 15,
            likes_count=10 + i * 2,
            comments_count=2 + i
        )
    print('创建文章完成')

print()
print('最终统计:')
print('管理员用户存在:', User.objects.filter(username='admin').exists())
print('文章数量:', Article.objects.count())
print('分类数量:', Category.objects.count())
print('标签数量:', Tag.objects.count())
