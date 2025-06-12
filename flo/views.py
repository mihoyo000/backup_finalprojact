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
    # 공지사항(is_notice=True)을 제외하고, 일반 게시글 중에서
    # 0. 좋아요 수가 1 이상인 게시물만 대상 (새로운 조건)
    # 1. 좋아요 많은 순
    # 2. (좋아요 수 같을 시) 조회수 많은 순
    # 3. (좋아요 수, 조회수 같을 시) 최신순
    top_posts = Post.objects.filter(
        is_notice=False
    ).annotate(
        num_likes=Count('likes', distinct=True),
        num_comments=Count('comments', distinct=True)
    ).filter(
        num_likes__gt=0  # ★★★ 추가된 조건: 좋아요 수가 0보다 큰 게시물만 필터링 ★★★
    ).select_related(
        'author__profile'
    ).prefetch_related(
        Prefetch('categories', queryset=Category.objects.order_by('name'))
    ).order_by(
        '-num_likes',  # 1. 좋아요 많은 순
        '-views',      # 2. 조회수 많은 순 (좋아요 수가 같을 경우 이 기준으로 정렬)
        '-created_at'  # 3. 최신순 (좋아요 수와 조회수 모두 같을 경우 이 기준으로 정렬)
    )[:3]

    context = {
        'top_posts': top_posts
    }
    return render(request, 'flo/index.html', context)

# --- 로그인 뷰 ---
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

# --- 로그아웃 뷰 ---
@login_required
def logout_view(request):
    if request.method == 'POST':
        username = request.user.username
        auth_logout(request)
        messages.info(request, f'{username}님, 성공적으로 로그아웃되었습니다.')
        return redirect('flo:home')
    else:
        # GET 요청으로 로그아웃 URL 직접 접근 시, 홈페이지 등으로 리디렉션 또는 에러 메시지
        # 일반적으로는 base.html에서 form으로 POST 요청을 하므로 이 경우는 거의 없음
        return redirect('flo:home')

# 학습 게시판 목록 (study_post_list.html)
def study_post_list(request):
    posts_page_obj = None # 변수 초기화
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
        posts_page_obj = paginator.page(page_number) # ★★★ 변수명 posts_page_obj로 통일 ★★★
    except PageNotAnInteger:
        posts_page_obj = paginator.page(1) # ★★★ 변수명 posts_page_obj로 통일 ★★★
    except EmptyPage:
        posts_page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1) # ★★★ 변수명 posts_page_obj로 통일 ★★★

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
    sort_order = request.GET.get('sort', 'created_at') # 기본 정렬: 등록순

    if sort_order == '-created_at': # 최신순
        comments_qs = post.comments.order_by('-created_at').select_related('author__profile')
    else: # 등록순 (기본)
        comments_qs = post.comments.order_by('created_at').select_related('author__profile')

    # 댓글 데이터를 JSON으로 직렬화하기 좋은 형태로 가공
    comments_data = []
    for comment in comments_qs:
        author_profile_image_url = None
        if comment.author.profile.has_custom_profile_image:
            author_profile_image_url = comment.author.profile.get_profile_image_url
        # else: # 기본 프로필 이미지는 클라이언트에서 처리 가능
            # author_profile_image_url = request.build_absolute_uri(settings.STATIC_URL + 'flo/images/icons/profile/default_profile_light.png') # 필요시

        comments_data.append({
            'id': comment.id,
            'author_display_name': comment.author.profile.get_display_name,
            'author_profile_image_url': author_profile_image_url,
            'has_custom_profile_image': comment.author.profile.has_custom_profile_image,
            'content': comment.content, # 원본 content (JS에서 linebreaksbr 처리)
            'created_at': comment.created_at.strftime("%Y-%m-%d %H:%M"),
            'can_edit_delete': request.user.is_authenticated and request.user == comment.author,
            # 수정/삭제 URL은 클라이언트에서 생성하거나 여기서 미리 만들어 전달
            'edit_url': reverse('flo:study_post_comment_edit', args=[comment.pk]),
            'delete_url': reverse('flo:study_post_comment_delete', args=[comment.pk]),
        })

    return JsonResponse({'comments': comments_data})


# 기존 study_post_detail 뷰는 초기 로드 시 댓글 정렬을 적용하도록 수정
def study_post_detail(request, pk):
    post = get_object_or_404(
        Post.objects.select_related('author').prefetch_related('likes', 'categories'), # comments는 아래에서 정렬
        pk=pk
    )
    comment_form = CommentForm()

    # --- 조회수 증가 로직 ---
    post.views += 1
    post.save(update_fields=['views'])

    # 초기 댓글 정렬 (기본: 등록순)
    # URL 파라미터로 sort를 받을 수도 있지만, AJAX로 처리하므로 초기엔 고정하거나 세션/쿠키로 기억
    initial_sort_order = request.GET.get('sort', 'created_at') # 또는 'created_at' 고정
    if initial_sort_order == '-created_at':
        comments = post.comments.order_by('-created_at').select_related('author__profile')
    else:
        comments = post.comments.order_by('created_at').select_related('author__profile')


    is_liked = False
    if request.user.is_authenticated and post.likes.filter(pk=request.user.pk).exists():
        is_liked = True

    context = {
        'post': post,
        'comments': comments, # 정렬된 댓글 전달
        'comment_form': comment_form,
        'is_liked': is_liked,
        'current_sort_order': initial_sort_order, # 현재 정렬 상태 전달 (JS에서 초기 active 클래스 설정용)
    }
    return render(request, 'flo/study_post/study_post_detail.html', context)

# 글쓰기 (post_form.html)
@login_required
def study_post_create(request):
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')
    AttachmentFormSet = inlineformset_factory(Post, Attachment, form=AttachmentForm, fk_name='post', extra=1, can_delete=True)

    if request.method == 'POST':
        print("--- CREATE POST: POST request data ---")
        print("REQUEST.POST:", request.POST)

        form = PostForm(request.POST, request.FILES)
        formset = AttachmentFormSet(request.POST, request.FILES, prefix='attachments')

        if form.is_valid() and formset.is_valid():
            print("--- CREATE POST: Form and Formset are VALID ---")
            print("Form cleaned_data['categories']:", form.cleaned_data.get('categories'))

            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m() # ManyToManyField (categories) 저장

            saved_attachments = formset.save(commit=False)
            for attachment in saved_attachments:
                attachment.post = post
                attachment.save()

            messages.success(request, '게시글이 성공적으로 등록되었습니다.')
            return redirect(post.get_absolute_url())
        else: # 폼 유효성 검사 실패 시
            print("--- CREATE POST: Form or Formset INVALID ---")
            if not form.is_valid():
                print("PostForm errors:", form.errors.as_json(escape_html=True))
            if not formset.is_valid():
                print("AttachmentFormSet errors:")
                for i, fs_form_errors in enumerate(formset.errors):
                    if fs_form_errors:
                        print(f"  Form {i} errors: {fs_form_errors.as_json(escape_html=True)}")
                print(f"  AttachmentFormSet non_form_errors: {formset.non_form_errors().as_json(escape_html=True)}")
            
            # ★★★ POST 실패 시에도 initial_selected_categories_for_js 정의 ★★★
            initial_selected_categories_for_js = [] # 글쓰기 시 POST 실패는 선택된 카테고리가 없으므로 빈 리스트
            
            # POST 실패 시에도 major_categories를 가공해서 전달
            processed_major_categories_for_form = []
            for major_cat in major_categories_list:
                processed_major_categories_for_form.append({
                    'id': major_cat.id,
                    'name': major_cat.name,
                    'slug': major_cat.slug,
                    'children_exists': major_cat.children.exists(),
                    'is_leaf': major_cat.is_leaf_node()
                })

            context = { # POST 실패 시 context 재구성
                'form': form,
                'formset': formset,
                'form_title': '학습 게시판 글쓰기',
                'submit_text': '등록',
                'major_categories': processed_major_categories_for_form, # 가공된 데이터 전달
                'initial_selected_categories_for_js': json.dumps(initial_selected_categories_for_js, cls=DjangoJSONEncoder)
            }
            return render(request, 'flo/study_post/study_post_form.html', context) # render로 context 전달

    else: # GET 요청 (글쓰기 폼을 처음 보여줄 때)
        form = PostForm()
        formset = AttachmentFormSet(prefix='attachments')
        initial_selected_categories_for_js = [] # 글쓰기 시에는 빈 배열
        
        # GET 요청 시 major_categories 가공
        processed_major_categories_for_form = []
        for major_cat in major_categories_list:
            processed_major_categories_for_form.append({
                'id': major_cat.id,
                'name': major_cat.name,
                'slug': major_cat.slug,
                'children_exists': major_cat.children.exists(),
                'is_leaf': major_cat.is_leaf_node()
            })

        context = {
            'form': form,
            'formset': formset,
            'form_title': '학습 게시판 글쓰기',
            'submit_text': '등록',
            'major_categories': processed_major_categories_for_form, # 가공된 데이터 전달
            'initial_selected_categories_for_js': json.dumps(initial_selected_categories_for_js, cls=DjangoJSONEncoder)
        }
        return render(request, 'flo/study_post/study_post_form.html', context)

def ajax_get_child_categories(request):
    parent_id = request.GET.get('parent_id')
    children_data = []
    if parent_id:
        try:
            parent_category = Category.objects.get(id=parent_id)
            children = parent_category.children.all().order_by('name') # related_name 'children' 사용
            for child in children:
                children_data.append({
                    'id': child.id,
                    'name': child.name,
                    'slug': child.slug,
                    'full_path': child.get_full_path_name, # ★★★ @property이므로 () 없이 접근
                    'has_children': not child.is_leaf_node(), # is_leaf_node()의 반대
                    'is_leaf': child.is_leaf_node() # JS에서 data-is-leaf로 사용
                })
        except Category.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error in ajax_get_child_categories: {e}") # 디버깅용
            pass
    return JsonResponse({'children': children_data})

# AJAX로 하위 카테고리 목록을 가져오는 뷰
def ajax_search_categories(request):
    query = request.GET.get('q', '').strip()
    page = request.GET.get('page', 1)
    ITEMS_PER_PAGE = 15
    current_page_num = int(page)

    categories_data = []
    has_next_page = False
    total_results_count = 0

    if query:
        # 1단계: 검색어(query)와 이름이 일치하는 모든 카테고리(대/중/소 무관)를 찾습니다.
        # prefetch_related를 사용하여 get_leaf_nodes 호출 시 DB 접근을 줄이도록 시도합니다.
        # 깊이가 깊은 경우, 이 prefetch만으로는 부족할 수 있습니다.
        matched_categories_qs = Category.objects.annotate(
            name_lower=Lower('name')
        ).filter(
            name_lower__icontains=query
        ).prefetch_related( # 재귀 호출에 대비한 prefetch
            Prefetch('children', queryset=Category.objects.all().prefetch_related(
                Prefetch('children', queryset=Category.objects.all().prefetch_related('children')) # 최대 3단계까지
            ))
        ).distinct() # 중복 제거 (필요시)

        # 2단계: 찾은 카테고리들 각각에 대해, 그 자신 또는 자손들 중 최하위 노드들을 수집합니다.
        leaf_categories_to_display = set()
        for category_match in matched_categories_qs:
            # 모델에 추가한 get_leaf_nodes() 메소드 사용
            leaves_from_match = category_match.get_leaf_nodes()
            leaf_categories_to_display.update(leaves_from_match)
        
        # 3단계: 수집된 최하위 카테고리들을 정렬하고 페이지네이션합니다.
        # Category 모델에 get_full_path_name @property가 있다고 가정
        all_sorted_leaf_categories = sorted(
            list(leaf_categories_to_display), 
            key=lambda cat: cat.get_full_path_name  # 정렬 기준
        )
        
        total_results_count = len(all_sorted_leaf_categories)

        paginator = Paginator(all_sorted_leaf_categories, ITEMS_PER_PAGE)
        try:
            results_page_obj = paginator.page(current_page_num)
        except PageNotAnInteger:
            results_page_obj = paginator.page(1)
            current_page_num = 1
        except EmptyPage:
            # 페이지 번호가 범위를 벗어난 경우, 마지막 페이지로 설정 (또는 1페이지로)
            results_page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)
            current_page_num = results_page_obj.number
        
        for cat in results_page_obj:
            categories_data.append({
                'id': cat.id,
                'name': cat.name, 
                'slug': cat.slug,
                'full_path': cat.get_full_path_name, # @property 호출
                'is_leaf': True, # 이 로직에서는 항상 leaf 노드만 반환
            })
        
        has_next_page = results_page_obj.has_next()

    return JsonResponse({
        'categories': categories_data,
        'has_next_page': has_next_page,
        'total_results': total_results_count,
        'current_page': current_page_num
    })

# 글 수정 (post_form.html)
@login_required
def study_post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    # major_categories_list는 Category 객체의 QuerySet
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')

    AttachmentFormSet = inlineformset_factory(
        Post, Attachment, form=AttachmentForm, fk_name='post', extra=1, can_delete=True
    )

    if request.user != post.author:
        messages.error(request, '수정 권한이 없습니다.')
        return redirect(post.get_absolute_url())

    if request.method == 'POST':
        print("--- EDIT POST: POST request data ---")
        print("REQUEST.POST:", request.POST)
        print("REQUEST.FILES:", request.FILES)

        form = PostForm(request.POST, request.FILES, instance=post)
        formset = AttachmentFormSet(
            request.POST,
            request.FILES,
            instance=post,
            prefix='attachments',
            queryset=post.post_attachments.all()
        )

        # ★★★ is_valid() 호출 전에 management_form 확인 ★★★
        print("--- study_post_edit: POST - Formset Management Data (before validation) ---")
        management_form_is_valid = formset.management_form.is_valid() # 먼저 is_valid() 호출
        print(f"  formset.management_form.is_valid(): {management_form_is_valid}")
        if not management_form_is_valid:
            print(f"  formset.management_form.errors: {formset.management_form.errors}")
        # management_form이 유효해야 cleaned_data 접근 가능
        if management_form_is_valid:
            print(f"  TOTAL_FORMS (from management_form.cleaned_data): {formset.management_form.cleaned_data.get('TOTAL_FORMS')}")
            print(f"  INITIAL_FORMS (from management_form.cleaned_data): {formset.management_form.cleaned_data.get('INITIAL_FORMS')}")
        else:
            print(f"  TOTAL_FORMS (from request.POST): {request.POST.get(formset.prefix + '-TOTAL_FORMS')}")
            print(f"  INITIAL_FORMS (from request.POST): {request.POST.get(formset.prefix + '-INITIAL_FORMS')}")


        # ★★★ is_valid() 호출 후 각 폼의 상태 확인 ★★★
        form_is_valid = form.is_valid()
        formset_is_valid = formset.is_valid() # is_valid()를 호출해야 cleaned_data 등이 채워짐

        print(f"Form is_valid: {form_is_valid}")
        print(f"Formset is_valid: {formset_is_valid}")


        print("--- study_post_edit: POST - Formset forms instances and cleaned_data (after validation attempt) ---")
        for i, fs_form in enumerate(formset.forms):
            instance_pk_in_view = getattr(fs_form.instance, 'pk', 'No PK Attr')
            has_changed = fs_form.has_changed()
            is_new = not fs_form.instance.pk if fs_form.instance else True
            can_delete_checked = False
            
            if formset.is_bound and fs_form.is_bound and not fs_form.errors:
                if 'DELETE' in fs_form.cleaned_data and fs_form.cleaned_data.get('DELETE'):
                    can_delete_checked = True
            elif 'DELETE' in fs_form.fields and fs_form.data.get(fs_form.prefix + '-DELETE'):
                can_delete_checked = True

            print(f"  Form {i} instance in view: {fs_form.instance}, PK: {instance_pk_in_view}, Has Changed: {has_changed}, Is New: {is_new}, DELETE checked: {can_delete_checked}")
            if fs_form.errors:
                print(f"    Form {i} errors: {fs_form.errors.as_json(escape_html=True)}")


        if form_is_valid and formset_is_valid:
            saved_post = form.save() # PostForm의 save()가 먼저 호출되어야 함 (m2m 필드 때문)
            formset.save()
            messages.success(request, '게시글이 성공적으로 수정되었습니다.')
            return redirect(saved_post.get_absolute_url())
        else:
            if not form_is_valid:
                print("--- PostForm errors on edit ---")
                print(form.errors.as_json(escape_html=True)) # PostForm 에러 확인
            if not formset_is_valid:
                print("--- AttachmentFormSet non_form_errors on edit ---")
                print(formset.non_form_errors().as_json(escape_html=True))
            messages.error(request, '게시글 수정에 실패했습니다. 입력 내용을 확인해주세요.')
            # ★★★ POST 실패 시에도 major_categories를 가공해서 전달해야 함 ★★★
            processed_major_categories_for_form = []
            for major_cat in major_categories_list:
                processed_major_categories_for_form.append({
                    'id': major_cat.id,
                    'name': major_cat.name,
                    'slug': major_cat.slug,
                    'children_exists': major_cat.children.exists(),
                    'is_leaf': major_cat.is_leaf_node()
                })
            # POST 실패 시 initial_selected_categories_for_js는 form.cleaned_data를 기반으로 다시 만들거나,
            # request.POST에서 직접 가져와서 JS가 처리하도록 할 수도 있습니다.
            # 여기서는 간단하게, form 인스턴스에 이미 설정된 categories를 사용합니다.
            current_post_for_initial_data = form.instance # 이미 instance=post로 초기화됨
            initial_selected_categories_for_js = []
            if current_post_for_initial_data and current_post_for_initial_data.pk:
                # form.cleaned_data.get('categories')는 QuerySet이므로 바로 사용 가능
                # 단, form.is_valid()가 False이면 cleaned_data에 categories가 없을 수 있으므로 주의
                # 여기서는 instance의 categories를 사용하는 것이 더 안전할 수 있음.
                selected_cats_from_form = form.cleaned_data.get('categories') if form_is_valid else current_post_for_initial_data.categories.all()

                initial_selected_categories_for_js = [
                    {'id': str(cat.id), 'name': cat.name, 'path': cat.get_full_path_name, 'slug': cat.slug}
                    for cat in selected_cats_from_form # 에러 시에는 form.instance.categories.all() 사용
                ]

            context = { # POST 실패 시 context 재구성
                'form': form,
                'formset': formset,
                'post': post,
                'form_title': '학습 게시판 - 게시글 수정',
                'submit_text': '수정',
                'major_categories': processed_major_categories_for_form, # 가공된 데이터 전달
                'initial_selected_categories_for_js': json.dumps(initial_selected_categories_for_js, cls=DjangoJSONEncoder),
            }
            return render(request, 'flo/study_post/study_post_form.html', context)


    else: # GET 요청 (수정 폼을 처음 보여줄 때)
        form = PostForm(instance=post) # instance=post 로 PostForm 초기화
        
        existing_attachments_list = list(post.post_attachments.all())
        for attachment_instance in existing_attachments_list:
            if attachment_instance.file:
                attachment_instance._display_filename = os.path.basename(attachment_instance.file.name)
            else:
                attachment_instance._display_filename = "파일 없음"

        formset = AttachmentFormSet(
            instance=post,
            prefix='attachments',
            queryset=Attachment.objects.filter(pk__in=[att.pk for att in existing_attachments_list])
        )
        
        for i, form_in_formset in enumerate(formset.forms):
            if i < len(existing_attachments_list):
                form_in_formset.instance._display_filename = existing_attachments_list[i]._display_filename
        
        initial_selected_categories_for_js = []
        # GET 요청 시에는 post 객체의 categories를 사용
        if post and post.pk:
            initial_selected_categories_for_js = [
                {'id': str(cat.id), 'name': cat.name, 'path': cat.get_full_path_name, 'slug': cat.slug}
                for cat in post.categories.all()
            ]
        
        # ★★★ GET 요청 시에도 major_categories를 가공해서 전달 ★★★
        processed_major_categories_for_form = []
        for major_cat in major_categories_list:
            processed_major_categories_for_form.append({
                'id': major_cat.id,
                'name': major_cat.name,
                'slug': major_cat.slug,
                'children_exists': major_cat.children.exists(),
                'is_leaf': major_cat.is_leaf_node()
            })

        context = {
            'form': form,
            'formset': formset,
            'post': post,
            'form_title': '학습 게시판 - 게시글 수정',
            'submit_text': '수정',
            'major_categories': processed_major_categories_for_form, # 가공된 데이터 전달
            'initial_selected_categories_for_js': json.dumps(initial_selected_categories_for_js, cls=DjangoJSONEncoder),
        }
        return render(request, 'flo/study_post/study_post_form.html', context)

# 글 삭제
@login_required
def study_post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user != post.author:
        messages.error(request, '삭제 권한이 없습니다.')
        return redirect(post.get_absolute_url()) # 또는 HttpResponseForbidden

    if request.method == 'POST': # POST 요청으로만 삭제
        post.delete()
        messages.success(request, '게시글이 삭제되었습니다.')
        return redirect('flo:study_post_list')
    else:
        # GET 요청 시 삭제 확인 페이지를 보여주거나, 바로 리디렉션 (보통 POST만 허용)
        return HttpResponseBadRequest("잘못된 요청입니다.")


# 글 좋아요
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

    if request.headers.get('x-requested-with') == 'XMLHttpRequest': # AJAX 요청인지 확인
        return JsonResponse({'liked': liked, 'count': post.total_likes})

    return redirect(post.get_absolute_url()) # AJAX 아닌 경우 상세 페이지로

# 댓글 작성
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
                # 사용자 프로필 정보 가져오기 (안전하게)
                author_display_name = comment.author.username # 기본값은 username
                author_profile_image_url = None # 기본값은 None (JS에서 기본 이미지 사용)
                
                # request.user.profile이 아닌 comment.author.profile을 사용해야 합니다.
                try:
                    profile = comment.author.profile # User와 Profile이 OneToOne으로 연결되어 있다고 가정
                    author_display_name = profile.get_display_name
                    if profile.has_custom_profile_image: # 커스텀 이미지가 있을 경우
                        author_profile_image_url = profile.get_profile_image_url
                    # else인 경우 author_profile_image_url은 None으로 유지되어 JS에서 기본 이미지 경로를 사용하게 됩니다.
                    # 또는 여기서 직접 기본 이미지 경로를 지정할 수도 있습니다.
                    # else:
                    #    author_profile_image_url = settings.STATIC_URL + 'flo/images/icons/profile/default_profile_light.png'
                except Profile.DoesNotExist: # Profile이 없는 예외적인 경우 처리
                    pass # 기본값 사용
                except AttributeError: # .profile 접근 시 발생할 수 있는 다른 에러
                    pass # 기본값 사용

                return JsonResponse({
                    'status': 'success',
                    'comment_id': comment.id,
                    'author_username': comment.author.username,
                    'author_display_name': author_display_name, # 추가된 정보
                    'author_profile_image_url': author_profile_image_url, # 추가된 정보
                    'content': comment.content, # HTML 렌더링용 (linebreaksbr 처리된)
                    'content_raw': comment.content, # 수정 폼에 들어갈 원본 내용
                    'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
                    'comment_count': post.comment_count,
                })
            messages.success(request, '댓글이 작성되었습니다.')
            return redirect(post.get_absolute_url() + f'#comment-{comment.id}')
    
    # AJAX 요청이 아니고, 폼 유효성 검사에 실패했거나 GET 요청일 경우
    # (이 부분은 현재 로직상 AJAX 실패 시 도달하지는 않을 것으로 보입니다.)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'error', 'errors': form.errors if 'form' in locals() else 'Unknown error'}, status=400)
    
    messages.error(request, '댓글 작성에 실패했습니다.')
    return redirect(post.get_absolute_url())


# 댓글 수정 (AJAX로 처리하는 것이 일반적)
@login_required
def study_post_comment_edit(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if request.user != comment.author:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)

    if request.method == 'POST':
        # content = request.POST.get('content') # AJAX 요청의 body에서 content 추출
        # if content:
        #     comment.content = content
        #     comment.save(update_fields=['content', 'updated_at'])
        #     return JsonResponse({
        #         'status': 'success',
        #         'content': comment.content,
        #         'updated_at': comment.updated_at.strftime('%Y-%m-%d %H:%M')
        #     })
        # return JsonResponse({'status': 'error', 'message': '내용이 없습니다.'}, status=400)
        form = CommentForm(request.POST, instance=comment) # 폼을 사용하는 경우
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

# 댓글 삭제 (AJAX로 처리하는 것이 일반적)
@login_required
def study_post_comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    post = comment.post # 삭제 후 게시글 댓글 수 업데이트 위해
    
    if request.user != comment.author:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': '삭제 권한이 없습니다.'}, status=403)
        messages.error(request, '삭제 권한이 없습니다.')
        return redirect(post.get_absolute_url())

    if request.method == 'POST':
        comment_id = comment.id # 삭제 전에 ID 저장
        comment.delete() # 실제 DB에서 삭제

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # 성공적으로 삭제되었으므로, JSON 응답 반환
            return JsonResponse({
                'status': 'success',
                'deleted_comment_id': comment_id, # 삭제된 댓글 ID 전달
                'comment_count': post.comment_count # 최신 댓글 수 전달
            })
        
        messages.success(request, '댓글이 삭제되었습니다.')
        return redirect(post.get_absolute_url())
    
    # POST 요청이 아닐 경우 (AJAX는 POST로 보내므로 이 경우는 드묾)
    return HttpResponseBadRequest("잘못된 요청입니다. POST 요청만 허용됩니다.")


# FAQ 목록 (faq.html)
def faq_list(request):
    all_faq_items_list_qs = FAQItem.objects.select_related('category').order_by('category_id', 'order', 'pk')

    paginator = Paginator(all_faq_items_list_qs, 5)
    page_number = request.GET.get('page')
    page_obj = None

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

    grouped_faq_list_for_template = []

    if page_obj and page_obj.object_list:
        # ★★★ page_obj.object_list를 명시적으로 Python 리스트로 변환 ★★★
        current_page_items_list = list(page_obj.object_list)

        # 이제 Python 리스트인 current_page_items_list를 사용하여 groupby 수행
        for category_obj, items_in_group_iter in groupby(current_page_items_list, key=lambda item: item.category):
            items_in_group = list(items_in_group_iter) # groupby 결과도 리스트로 변환
            show_more = False

            if page_obj.has_next():
                try:
                    next_page_check = paginator.page(page_obj.next_page_number())
                    # ★★★ current_page_items_list가 비어있지 않은지 확인 후 마지막 요소 접근 ★★★
                    if items_in_group and current_page_items_list and items_in_group[-1] == current_page_items_list[-1]:
                        if any(item.category_id == category_obj.id for item in next_page_check.object_list):
                            show_more = True
                except EmptyPage:
                    pass # 다음 페이지가 비어있는 경우는 로직상 문제 없음
            
            grouped_faq_list_for_template.append({
                'grouper': category_obj,
                'list': items_in_group,
                'show_more_indicator': show_more,
            })

    context = {
        'page_obj': page_obj,
        'category_list_from_view': grouped_faq_list_for_template,
    }
    return render(request, 'flo/faq/faq.html', context)
