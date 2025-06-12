# flo/views.py
import os
from django.conf import settings
from django.urls import reverse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Prefetch
from django.db.models.functions import Lower, Coalesce
from django.db.models import Value
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.contrib import messages
from .models import Post, Attachment, Comment, Category, FAQCategory, FAQItem, Profile
from .forms import PostForm, AttachmentForm, CommentForm
from django.forms import inlineformset_factory
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.template.loader import render_to_string
from itertools import groupby

def home(request):
    # 인기 게시글 Top 3 가져오기
    top_posts = Post.objects.filter(
        is_notice=False
    ).annotate(
        num_likes=Count('likes', distinct=True),
        num_comments=Count('comments', distinct=True)
    ).filter(
        num_likes__gt=0
    ).select_related(
        'author__profile'
    ).prefetch_related(
        Prefetch('categories', queryset=Category.objects.order_by('name'))
    ).order_by(
        '-num_likes',
        '-views',
        '-created_at'
    )[:3]

    context = {
        'top_posts': top_posts
    }
    return render(request, 'flo/index.html', context)

def login_view(request):
    if request.user.is_authenticated:
        return redirect('flo:home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'{user.username}님, 로그인되었습니다.'
                })
            messages.success(request, f'{user.username}님, 로그인되었습니다.')
            next_url = request.GET.get('next')
            return redirect(next_url or 'flo:home')
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': '아이디 또는 비밀번호가 올바르지 않습니다.'
                })
            messages.error(request, '아이디 또는 비밀번호가 올바르지 않습니다.')
    else:
        form = AuthenticationForm()
    return render(request, 'flo/auth/login.html', {'form': form, 'next': request.GET.get('next', '')})

@login_required
def logout_view(request):
    if request.method == 'POST':
        username = request.user.username
        auth_logout(request)
        messages.info(request, f'{username}님, 성공적으로 로그아웃되었습니다.')
        return redirect('flo:home')
    else:
        return redirect('flo:home')

def study_post_list(request):
    posts_page_obj = None
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')

    selected_slugs_str = request.GET.get('category_slugs', '')
    selected_slug_list = [slug.strip() for slug in selected_slugs_str.split(',') if slug.strip()]

    post_query = Post.objects.select_related('author__profile').prefetch_related(
        'categories', 'likes', 'comments'
    ).annotate(
        annotated_comment_count=Count('comments', distinct=True),
        annotated_total_likes=Count('likes', distinct=True)
    ).order_by('-is_notice', '-created_at')

    if selected_slug_list:
        post_query = post_query.filter(categories__slug__in=selected_slug_list).distinct()

    search_type = request.GET.get('search_type', '')
    search_keyword = request.GET.get('search_keyword', '')
    category_q = request.GET.get('category_q', '')

    if search_keyword:
        if search_type == 'title_content':
            post_query = post_query.filter(Q(title__icontains=search_keyword) | Q(content__icontains=search_keyword))
        elif search_type == 'title':
            post_query = post_query.filter(title__icontains=search_keyword)
        elif search_type == 'author':
            post_query = post_query.filter(
                Q(author__username__icontains=search_keyword) |
                Q(author__profile__nickname__icontains=search_keyword)
            )
        elif search_type == 'category_name':
            post_query = post_query.filter(categories__name__icontains=search_keyword).distinct()

    paginator = Paginator(post_query, 10)
    page_number = request.GET.get('page')
    try:
        posts_page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        posts_page_obj = paginator.page(1)
    except EmptyPage:
        posts_page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        posts_html = render_to_string(
            'flo/study_post/_study_post_list_items.html',
            {'posts': posts_page_obj, 'request': request}
        )
        pagination_html = render_to_string(
            'flo/study_post/_pagination.html',
            {'posts': posts_page_obj, 'request': request, 'current_category_slugs_str': selected_slugs_str, 'search_keyword': search_keyword, 'search_type': search_type, 'category_q': category_q }
        )
        return JsonResponse({
            'posts_html': posts_html,
            'pagination_html': pagination_html,
        })

    initial_selected_categories_for_ui = []
    if selected_slug_list:
        selected_cats_qs = Category.objects.filter(slug__in=selected_slug_list)
        for cat in selected_cats_qs:
            ancestors = cat.get_ancestors()
            initial_selected_categories_for_ui.append({
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug,
                'get_full_path_name': cat.get_full_path_name(),
                'ancestry_slugs': [anc.slug for anc in ancestors],
                'is_leaf': cat.is_leaf_node()
            })

    processed_major_categories = []
    for major_cat in major_categories_list:
        processed_major_categories.append({
            'id': major_cat.id,
            'name': major_cat.name,
            'slug': major_cat.slug,
            'children_exists': major_cat.children.exists(),
            'is_leaf': major_cat.is_leaf_node()
        })

    context = {
        'posts': posts_page_obj,
        'major_categories': processed_major_categories,
        'initial_selected_categories_for_ui': initial_selected_categories_for_ui,
        'current_category_slugs_str': selected_slugs_str,
        'search_type': search_type,
        'search_keyword': search_keyword,
        'category_q': category_q,
    }
    return render(request, 'flo/study_post/study_post_list.html', context)

def ajax_get_comments(request, post_pk):
    post = get_object_or_404(Post, pk=post_pk)
    sort_order = request.GET.get('sort', 'created_at')

    if sort_order == '-created_at':
        comments_qs = post.comments.order_by('-created_at').select_related('author__profile')
    else:
        comments_qs = post.comments.order_by('created_at').select_related('author__profile')

    comments_data = []
    for comment in comments_qs:
        author_profile_image_url = None
        if comment.author.profile.has_custom_profile_image:
            author_profile_image_url = comment.author.profile.get_profile_image_url

        comments_data.append({
            'id': comment.id,
            'author_display_name': comment.author.profile.get_display_name,
            'author_profile_image_url': author_profile_image_url,
            'has_custom_profile_image': comment.author.profile.has_custom_profile_image,
            'content': comment.content,
            'created_at': comment.created_at.strftime("%Y-%m-%d %H:%M"),
            'can_edit_delete': request.user.is_authenticated and request.user == comment.author,
            'edit_url': reverse('flo:study_post_comment_edit', args=[comment.pk]),
            'delete_url': reverse('flo:study_post_comment_delete', args=[comment.pk]),
        })

    return JsonResponse({'comments': comments_data})

def study_post_detail(request, pk):
    post = get_object_or_404(
        Post.objects.select_related('author').prefetch_related('likes', 'categories'),
        pk=pk
    )
    comment_form = CommentForm()

    post.views += 1
    post.save(update_fields=['views'])

    initial_sort_order = request.GET.get('sort', 'created_at')
    if initial_sort_order == '-created_at':
        comments = post.comments.order_by('-created_at').select_related('author__profile')
    else:
        comments = post.comments.order_by('created_at').select_related('author__profile')

    is_liked = False
    if request.user.is_authenticated and post.likes.filter(pk=request.user.pk).exists():
        is_liked = True

    context = {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
        'is_liked': is_liked,
        'current_sort_order': initial_sort_order,
    }
    return render(request, 'flo/study_post/study_post_detail.html', context)

@login_required
def study_post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()  # 다대다 관계 저장 (카테고리)

            # 파일 첨부 처리
            files = request.FILES.getlist('files')
            for file in files:
                attachment = Attachment(post=post, file=file)
                attachment.save()

            messages.success(request, '게시글이 성공적으로 등록되었습니다.')
            return redirect(post.get_absolute_url())
    else:
        form = PostForm()
    context = {
        'form': form,
        'form_title': '학습 게시판 글쓰기',
        'submit_text': '등록',
    }
    return render(request, 'flo/study_post/study_post_form.html', context)

def ajax_get_child_categories(request):
    parent_slug = request.GET.get('parent_slug')
    if not parent_slug:
        return JsonResponse({'error': '부모 카테고리 slug가 필요합니다.'}, status=400)

    parent_category = get_object_or_404(Category, slug=parent_slug)
    child_categories = parent_category.children.all().order_by('name')

    categories_data = []
    for category in child_categories:
        categories_data.append({
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'has_children': category.children.exists(),
            'is_leaf': category.is_leaf_node()
        })

    return JsonResponse({'categories': categories_data})

def ajax_search_categories(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'categories': []})

    categories = Category.objects.filter(name__icontains=query).order_by('name')
    categories_data = []
    for category in categories:
        ancestors = category.get_ancestors()
        categories_data.append({
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'get_full_path_name': category.get_full_path_name(),
            'ancestry_slugs': [anc.slug for anc in ancestors],
            'is_leaf': category.is_leaf_node()
        })

    return JsonResponse({'categories': categories_data})

@login_required
def study_post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user != post.author:
        messages.error(request, '수정 권한이 없습니다.')
        return redirect(post.get_absolute_url())

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            form.save_m2m()  # 다대다 관계 저장 (카테고리)

            # 파일 첨부 처리
            files = request.FILES.getlist('files')
            for file in files:
                attachment = Attachment(post=post, file=file)
                attachment.save()

            messages.success(request, '게시글이 성공적으로 수정되었습니다.')
            return redirect(post.get_absolute_url())
    else:
        form = PostForm(instance=post)
    context = {
        'form': form,
        'post': post,
        'form_title': '학습 게시판 - 게시글 수정',
        'submit_text': '수정',
    }
    return render(request, 'flo/study_post/study_post_form.html', context)

@login_required
def study_post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user != post.author:
        messages.error(request, '삭제 권한이 없습니다.')
        return redirect(post.get_absolute_url())

    if request.method == 'POST':
        post.delete()
        messages.success(request, '게시글이 삭제되었습니다.')
        return redirect('flo:study_post_list')
    else:
        return HttpResponseBadRequest("잘못된 요청입니다.")

@login_required
def study_post_like(request, pk):
    post = get_object_or_404(Post, pk=pk)
    user = request.user

    if post.likes.filter(pk=user.pk).exists():
        post.likes.remove(user)
        liked = False
    else:
        post.likes.add(user)
        liked = True

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'liked': liked, 'count': post.total_likes})

    return redirect(post.get_absolute_url())

@login_required
def study_post_comment_create(request, post_pk):
    post = get_object_or_404(Post, pk=post_pk)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'comment_id': comment.id,
                    'author_display_name': comment.author.profile.get_display_name,
                    'content': comment.content,
                    'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
                    'comment_count': post.comment_count,
                })
            messages.success(request, '댓글이 작성되었습니다.')
            return redirect(post.get_absolute_url() + f'#comment-{comment.id}')
    messages.error(request, '댓글 작성에 실패했습니다.')
    return redirect(post.get_absolute_url())

@login_required
def study_post_comment_edit(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if request.user != comment.author:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)

    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'content': comment.content,
                    'updated_at': comment.updated_at.strftime('%Y-%m-%d %H:%M')
                })
            return redirect(comment.post.get_absolute_url() + f'#comment-{comment.id}')
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    return HttpResponseBadRequest("잘못된 요청입니다.")

@login_required
def study_post_comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    post = comment.post
    if request.user != comment.author:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
        messages.error(request, '삭제 권한이 없습니다.')
        return redirect(post.get_absolute_url())

    if request.method == 'POST':
        comment_id = comment.id
        comment.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'deleted_comment_id': comment_id, 'comment_count': post.comment_count})
        messages.success(request, '댓글이 삭제되었습니다.')
        return redirect(post.get_absolute_url())
    return HttpResponseBadRequest("잘못된 요청입니다.")

def faq_list(request):
    faq_categories_with_items = FAQCategory.objects.prefetch_related('faq_items').all()
    return render(request, 'flo/faq.html', {'faq_categories': faq_categories_with_items})