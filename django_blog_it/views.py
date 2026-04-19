from django.shortcuts import render, get_object_or_404, redirect
from django_blog_it.models import (BlogUser, Category, Tag, Article, 
                                     Comment, Like, Favorite, Follow, UserProfile)
from django_blog_it.forms import CategoryForm, ArticleForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.http.response import JsonResponse
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.views.decorators.http import require_POST, require_GET


def required_roles(roles):
    def user_role(function):
        def wrap(request, *args, **kwargs):
            user = BlogUser.objects.filter(
                user=request.user, is_active=True).values_list(
                'role', flat=True)
            for role in user:
                if (role in roles) or (
                        'admin' in roles and request.user.is_superuser):
                    return function(request, *args, **kwargs)
            raise Http404
        return wrap
    return user_role


@login_required
def dashboard(request):
    return render(request, 'django_blog_it/admin/dashboard.html')


@login_required
@required_roles(["admin", 'blog_admin'])
def user_list(request):
    total_users = get_user_model().objects.all()
    page = request.GET.get('page', 1)
    if request.GET.get('name'):
        name = request.GET.get('name')
        total_users = total_users.filter(email__icontains=name)
    if request.GET.get('page_length'):
        length = request.GET.get('page_length')
    else:
        length = 15
    paginator = Paginator(total_users, length)
    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        users = paginator.page(paginator.num_pages)
    return render(request, 'django_blog_it/admin/user_list.html',
                  {'users': users, 'list_length': length})


@login_required
@required_roles(["admin", 'blog_admin'])
def user_role(request):
    if request.method == "POST":
        role = request.POST.get('role')
        user = request.POST.get('user_id')
        if role:
            if not BlogUser.objects.filter(user_id=user, role=role).exists():
                BlogUser.objects.create(user_id=user, role=role)
        return JsonResponse({"response": 'done'})
    else:
        user_id = request.GET.get('user_id')
        role = request.GET.get('role')
        blog = BlogUser.objects.filter(user_id=user_id, role=role).first()
        blog.delete()
        return JsonResponse({"response": 'done'})


@login_required
@required_roles(["admin", "blog_admin", 'blog_publisher', 'blog_author'])
def blog_list(request):
    article_data = Article.objects.order_by('id')
    if request.GET.get('name'):
        name = request.GET.get('name')
        article_data = article_data.filter(
            title__icontains=name)
    blogs_list = article_data.filter(is_page=False)
    pages_list = article_data.filter(is_page=True)
    return render(
        request, 'django_blog_it/admin/blog_list.html', {'blogs_list': blogs_list, 'pages_list': pages_list})


@login_required
@required_roles(["admin", 'blog_admin', 'blog_publisher', 'blog_author'])
def blog_new(request):
    category_list = Category.objects.filter(created_by=request.user)
    tag_ids = Article.objects.values_list("tags", flat=True)
    tags = Tag.objects.filter(id__in=tag_ids)
    if request.method == 'POST':
        form = ArticleForm(request.POST, type=request.POST.get('is_page'))
        if form.is_valid():
            blog = form.save(commit=False)
            blog.created_by = request.user
            if request.POST.get('category'):
                blog.category = Category.objects.filter(
                    id=request.POST['category']).first()
            if request.POST.get('is_page') == "Page":
                blog.is_page = True
            else:
                blog.is_page = False
            blog.save()
            if request.POST.getlist('tags'):
                splitted_tags = request.POST.getlist("tags")
                for t in splitted_tags:
                    tag = Tag.objects.filter(name=t.lower())
                    if tag:
                        tag = tag[0]
                    else:
                        tag = Tag.objects.create(name=t.lower())
                    blog.tags.add(tag)
            return redirect('django_blog_it:blog_list')
        return render(request, 'django_blog_it/admin/blog_new.html', {'category': category_list, 'form': form.errors, 'tags': tags})
    return render(request, 'django_blog_it/admin/blog_new.html', {'category': category_list, 'tags': tags})


@login_required
@required_roles(["admin", 'blog_admin', 'blog_publisher', 'blog_author'])
def blog_edit(request, pk):
    blog_content = get_object_or_404(Article, id=pk)
    category_list = Category.objects.filter(
        created_by=request.user)
    tag_ids = Article.objects.filter(
        created_by=request.user).values_list("tags", flat=True)
    tags = Tag.objects.filter(id__in=tag_ids)
    if request.method == 'POST':
        form = ArticleForm(request.POST, instance=blog_content,
                           type=request.POST.get('is_page'))
        if form.is_valid():
            blog = form.save(commit=False)
            if request.POST.get("is_page") == "Page":
                blog.is_page = True
            else:
                blog.is_page = False
            blog.save()
            if request.POST.getlist('tags'):
                blog_content.tags.clear()
                tags = request.POST.getlist('tags')
                for t in tags:
                    tag = Tag.objects.filter(name=t.lower())
                    if tag:
                        tag = tag[0]
                    else:
                        tag = Tag.objects.create(name=t.lower())
                    blog.tags.add(tag)
            return redirect('django_blog_it:blog_list')
        return render(request, 'django_blog_it/admin/blog_edit.html', {'form': form.errors, 'blog': blog_content, 'category': category_list, 'tags': tags})
    return render(request, 'django_blog_it/admin/blog_edit.html', {'blog': blog_content, 'category': category_list, 'tags': tags})


@login_required
@required_roles(["admin", 'blog_admin', 'blog_publisher', 'blog_author'])
def blog_delete(request, pk):
    blog = get_object_or_404(Article, id=pk)
    blog.delete()
    return redirect('django_blog_it:blog_list')


@login_required
@required_roles(["admin", 'blog_admin', 'blog_publisher', 'blog_author'])
def blog_category_list(request):
    category_list = Category.objects.order_by('id')
    page = request.GET.get('page', 1)
    if request.GET.get('name'):
        name = request.GET.get('name')
        category_list = category_list.filter(name__icontains=name)
    if request.GET.get('page_length'):
        length = request.GET.get('page_length')
    else:
        length = 15
    paginator = Paginator(category_list, length)
    try:
        blog = paginator.page(page)
    except PageNotAnInteger:
        blog = paginator.page(1)
    except EmptyPage:
        blog = paginator.page(paginator.num_pages)
    return render(request, 'django_blog_it/admin/blog_category_list.html', {'blogdata': blog, 'list_length': length})


@login_required
@required_roles(["admin", 'blog_admin', 'blog_publisher', 'blog_author'])
def blog_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            blog = form.save(commit=False)
            blog.created_by = request.user
            blog.is_active = True
            blog.save()
            return redirect('django_blog_it:blog_category_list')
        return render(request, 'django_blog_it/admin/blog_category_create.html', {'form': form.errors
                                                                                  })
    return render(request, 'django_blog_it/admin/blog_category_create.html')


@login_required
@required_roles(["admin", 'blog_admin', 'blog_publisher', 'blog_author'])
def blog_catergory_edit(request, pk):
    blog = get_object_or_404(Category, id=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=blog)
        if form.is_valid():
            form.save()
            return redirect('django_blog_it:blog_category_list')
        return render(request, 'django_blog_it/admin/blog_category_edit.html',
                      {'form': form.errors, 'blog_data': blog})
    return render(request, 'django_blog_it/admin/blog_category_edit.html', {'blog_data': blog})


@login_required
@required_roles(["admin", 'blog_admin', 'blog_publisher', 'blog_author'])
def blog_category_delete(request, pk):
    blog = get_object_or_404(Category, id=pk)
    blog.delete()
    return redirect('django_blog_it:blog_category_list')


@login_required
@required_roles(["admin", 'blog_admin', 'blog_publisher', 'blog_author'])
def page_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            blog = form.save(commit=False)
            blog.created_by = request.user
            blog.is_active = True
            blog.is_page = True
            blog.save()
            return redirect('django_blog_it:page_category_list')
        return render(request, 'django_blog_it/admin/page_category.html', {'form': form.errors
                                                                           })
    return render(request, 'django_blog_it/admin/page_category.html')


@login_required
def blog_detail(request, slug):
    blog = get_object_or_404(Article, slug=slug, is_page=False)
    return render(request, 'django_blog_it/blog/blog.html', {'data': blog})


@login_required
def blog_preview(request, pk):
    blog = get_object_or_404(Article, id=pk)
    return render(request, 'django_blog_it/admin/preview.html', {'data': blog})


@login_required
def page_detail(request, slug):
    blog = get_object_or_404(Article, slug=slug, is_page=True)
    return render(request, 'django_blog_it/page/page.html', {'data': blog})


@login_required
def blog_content_edit_with_grapejs(request, pk):
    blog = get_object_or_404(Article, pk=pk)
    if request.method == "GET":
        landinpage_url = reverse(
            "django_blog_it:get_blog_content", kwargs={"pk": pk}
        )
        return render(
            request,
            "django_blog_it/admin/grape_js.html",
            {"landinpage_url": landinpage_url},
        )
    if request.method == "POST":
        html = request.POST.get("html")
        css = request.POST.get("css")
        if html and css:
            html_css = html + "<style>" + css + "</style>"
            blog.content = html_css
            blog.save()
        url = reverse("django_blog_it:blog_edit", kwargs={"pk": pk})
        return JsonResponse({"redirect_url": url})


@login_required
def get_blog_content(request, pk):
    blog = get_object_or_404(Article, pk=pk)
    if request.method == "POST":
        html = blog.content
        return JsonResponse({"html": html})
    return render(request, 'django_blog_it/admin/preview.html', {"data": blog})


@login_required
def blog_content_edit_with_ckeditor(request, pk):
    blog = get_object_or_404(Article, pk=pk)
    if request.method == "GET":
        return render(
            request,
            "django_blog_it/admin/ckeditor.html", {"blog": blog}
        )
    if request.method == "POST":
        content = request.POST.get("content")
        if content:
            blog.content = content
            blog.save()
        url = reverse("django_blog_it:blog_edit", kwargs={"pk": pk})
        return JsonResponse({"redirect_url": url})


def home(request):
    articles = Article.objects.filter(is_page=False, status='Published').order_by('-created_on')
    categories = Category.objects.annotate(article_count=Count('article')).filter(article_count__gt=0)
    tags = Tag.objects.annotate(article_count=Count('related_posts')).filter(article_count__gt=0)
    popular_articles = Article.objects.filter(is_page=False, status='Published').order_by('-views')[:5]
    
    context = {
        'articles': articles,
        'categories': categories,
        'tags': tags,
        'popular_articles': popular_articles,
    }
    return render(request, 'django_blog_it/blog/blog_list.html', context)


@login_required
@require_POST
def add_comment(request, slug):
    article = get_object_or_404(Article, slug=slug)
    content = request.POST.get('content')
    parent_id = request.POST.get('parent_id')
    
    if not content:
        return JsonResponse({'success': False, 'error': 'Content is required'})
    
    parent_comment = None
    if parent_id:
        parent_comment = get_object_or_404(Comment, id=parent_id)
    
    comment = Comment.objects.create(
        article=article,
        user=request.user,
        content=content,
        parent=parent_comment
    )
    
    article.comments_count = article.comments.filter(parent=None, is_active=True).count()
    article.save(update_fields=['comments_count'])
    
    return JsonResponse({
        'success': True,
        'comment_id': comment.id,
        'user': request.user.username,
        'content': content,
        'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
        'parent_id': parent_id
    })


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    article = comment.article
    comment.delete()
    
    article.comments_count = article.comments.filter(parent=None, is_active=True).count()
    article.save(update_fields=['comments_count'])
    
    return JsonResponse({'success': True})


@require_GET
def get_comments(request, slug):
    article = get_object_or_404(Article, slug=slug)
    comments = article.comments.filter(parent=None, is_active=True).order_by('-created_at')
    
    comments_data = []
    for comment in comments:
        comment_data = {
            'id': comment.id,
            'user': comment.user.username,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
            'likes_count': comment.likes_count,
            'replies': []
        }
        for reply in comment.get_replies():
            comment_data['replies'].append({
                'id': reply.id,
                'user': reply.user.username,
                'content': reply.content,
                'created_at': reply.created_at.strftime('%Y-%m-%d %H:%M'),
                'likes_count': reply.likes_count
            })
        comments_data.append(comment_data)
    
    return JsonResponse({'comments': comments_data})


@login_required
@require_POST
def toggle_like(request):
    article_id = request.POST.get('article_id')
    comment_id = request.POST.get('comment_id')
    
    if article_id:
        article = get_object_or_404(Article, id=article_id)
        
        like, created = Like.objects.get_or_create(user=request.user, article=article)
        
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        
        article.refresh_from_db()
        
        response = JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': article.likes_count
        })
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    
    elif comment_id:
        comment = get_object_or_404(Comment, id=comment_id)
        like, created = Like.objects.get_or_create(user=request.user, comment=comment)
        
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        
        comment.refresh_from_db()
        
        response = JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': comment.likes_count
        })
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
@require_POST
def toggle_favorite(request, slug):
    article = get_object_or_404(Article, slug=slug)
    favorite, created = Favorite.objects.get_or_create(user=request.user, article=article)
    
    if not created:
        favorite.delete()
        favorited = False
    else:
        favorited = True
    
    article.refresh_from_db()
    
    response = JsonResponse({
        'success': True,
        'favorited': favorited,
        'favorites_count': article.favorites_count
    })
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def search_articles(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category')
    tag_id = request.GET.get('tag')
    
    articles = Article.objects.filter(is_page=False, status='Published')
    
    if query:
        articles = articles.filter(
            Q(title__icontains=query) | 
            Q(content__icontains=query) |
            Q(meta_keywords__icontains=query)
        )
    
    if category_id:
        articles = articles.filter(category_id=category_id)
    
    if tag_id:
        articles = articles.filter(tags__id=tag_id)
    
    categories = Category.objects.all()
    tags = Tag.objects.all()
    
    context = {
        'articles': articles,
        'query': query,
        'categories': categories,
        'tags': tags,
        'selected_category': category_id,
        'selected_tag': tag_id,
    }
    return render(request, 'django_blog_it/blog/search_results.html', context)


def user_profile(request, username):
    user = get_object_or_404(get_user_model(), username=username)
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    articles = Article.objects.filter(created_by=user, status='Published', is_page=False)
    favorites = Favorite.objects.filter(user=user).select_related('article')
    
    is_following = False
    if request.user.is_authenticated:
        is_following = Follow.objects.filter(follower=request.user, following=user).exists()
    
    context = {
        'profile_user': user,
        'profile': profile,
        'articles': articles,
        'favorites': favorites,
        'is_following': is_following,
        'followers_count': user.followers.count(),
        'following_count': user.following.count(),
    }
    return render(request, 'django_blog_it/user/profile.html', context)


@login_required
def edit_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        profile.bio = request.POST.get('bio', '')
        profile.website = request.POST.get('website', '')
        profile.location = request.POST.get('location', '')
        birth_date = request.POST.get('birth_date')
        if birth_date:
            profile.birth_date = birth_date
        if request.FILES.get('avatar'):
            profile.avatar = request.FILES['avatar']
        profile.save()
        return redirect('django_blog_it:user_profile', username=request.user.username)
    
    return render(request, 'django_blog_it/user/edit_profile.html', {'profile': profile})


@login_required
@require_POST
def toggle_follow(request, username):
    user_to_follow = get_object_or_404(get_user_model(), username=username)
    
    if request.user == user_to_follow:
        return JsonResponse({'success': False, 'error': 'Cannot follow yourself'})
    
    follow, created = Follow.objects.get_or_create(follower=request.user, following=user_to_follow)
    
    if not created:
        follow.delete()
        following = False
    else:
        following = True
    
    return JsonResponse({
        'success': True,
        'following': following,
        'followers_count': user_to_follow.followers.count()
    })


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_page=False, status='Published')
    article.increase_views()
    
    comments = article.comments.filter(parent=None, is_active=True).order_by('-created_at')
    
    actual_comments_count = comments.count()
    if article.comments_count != actual_comments_count:
        article.comments_count = actual_comments_count
        article.save(update_fields=['comments_count'])
    
    is_liked = False
    is_favorited = False
    
    if request.user.is_authenticated:
        is_liked = Like.objects.filter(user=request.user, article=article).exists()
        is_favorited = Favorite.objects.filter(user=request.user, article=article).exists()
    
    related_articles = Article.objects.filter(
        category=article.category,
        status='Published',
        is_page=False
    ).exclude(id=article.id)[:3]
    
    context = {
        'article': article,
        'comments': comments,
        'is_liked': is_liked,
        'is_favorited': is_favorited,
        'related_articles': related_articles,
    }
    return render(request, 'django_blog_it/blog/article_detail.html', context)


from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages


def user_login(request):
    if request.user.is_authenticated:
        return redirect('django_blog_it:home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            auth_login(request, user)
            messages.success(request, f'欢迎回来，{user.username}！')
            next_url = request.GET.get('next', 'django_blog_it:home')
            return redirect(next_url)
        else:
            messages.error(request, '用户名或密码错误，请重试。')
    
    return render(request, 'django_blog_it/auth/login.html')


def user_logout(request):
    auth_logout(request)
    messages.info(request, '您已成功退出登录。')
    return redirect('django_blog_it:home')
