# flo/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.contrib import messages
from .models import Post, Comment, Category, FAQCategory, FAQItem
from .forms import PostForm, CommentForm

def home(request):
    return render(request, 'flo/index.html')

# --- 로그인 뷰 ---
def login_view(request):
    if request.user.is_authenticated: # 이미 로그인한 사용자는 로그인 페이지 접근 불가
        return redirect('flo:home') # 또는 'flo:study_post_list'

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, f'{user.username}님, 로그인되었습니다.')
            next_url = request.GET.get('next')
            # settings.py의 LOGIN_REDIRECT_URL ('flo:study_post_list')로 리디렉션하거나 next 파라미터가 있으면 그곳으로
            return redirect(next_url or 'flo:study_post_list')
        else:
            # 폼 에러 (아이디/비번 틀림 등)는 AuthenticationForm이 처리
            messages.error(request, '아이디 또는 비밀번호가 올바르지 않습니다.')
    else:
        form = AuthenticationForm()
    # next 파라미터를 템플릿으로 전달하여 로그인 후 원래 가려던 페이지로 이동할 수 있도록 form action에 포함
    return render(request, 'flo/auth/login.html', {'form': form, 'next': request.GET.get('next', '')})


# --- 로그아웃 뷰 ---
@login_required # 로그아웃은 로그인된 사용자만
def logout_view(request):
    # POST 요청으로만 로그아웃을 처리하여 CSRF 공격 방지
    if request.method == 'POST':
        username = request.user.username # 로그아웃 전에 사용자 이름 저장 (메시지용)
        auth_logout(request)
        messages.info(request, f'{username}님, 성공적으로 로그아웃되었습니다.')
        # settings.py의 LOGOUT_REDIRECT_URL ('flo:study_post_list')로 리디렉션
        return redirect('flo:study_post_list')
    else:
        # GET 요청으로 로그아웃 URL 직접 접근 시, 홈페이지 등으로 리디렉션 또는 에러 메시지
        # 일반적으로는 base.html에서 form으로 POST 요청을 하므로 이 경우는 거의 없음
        return redirect('flo:study_post_list')

# 학습 게시판 목록 (study_post_list.html)
def study_post_list(request):
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')

    # --- URL 쿼리 파라미터에서 선택된 카테고리 슬러그 목록 가져오기 ---
    selected_slugs_str = request.GET.get('category_slugs', '')
    selected_slug_list = [slug.strip() for slug in selected_slugs_str.split(',') if slug.strip()]

    # --- 게시글 쿼리 ---
    post_query = Post.objects.select_related('author').prefetch_related('categories').annotate(
        num_comments=Count('comments', distinct=True),
        num_likes=Count('likes', distinct=True)
    ).order_by('-is_notice', '-created_at')

    # 선택된 카테고리가 있다면 해당 카테고리들 중 하나라도 포함된 게시글 필터링
    if selected_slug_list:
        post_query = post_query.filter(categories__slug__in=selected_slug_list).distinct()

    # --- 검색 처리 ---
    search_type = request.GET.get('search_type', '')
    search_keyword = request.GET.get('search_keyword', '')

    if search_keyword:
        if search_type == 'title_content':
            post_query = post_query.filter(Q(title__icontains=search_keyword) | Q(content__icontains=search_keyword))
        elif search_type == 'title':
            post_query = post_query.filter(title__icontains=search_keyword)
        elif search_type == 'author':
            post_query = post_query.filter(author__username__icontains=search_keyword)
        elif search_type == 'category_name': # 카테고리명으로 검색
            post_query = post_query.filter(categories__name__icontains=search_keyword).distinct()

    # --- 페이지네이션 ---
    paginator = Paginator(post_query, 10) # 한 페이지에 10개씩
    page_number = request.GET.get('page')
    try:
        posts = paginator.page(page_number)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)

    # --- 템플릿에 전달할 초기 선택된 카테고리 정보 (UI 표시용) ---
    # JavaScript에서 URL 파라미터를 직접 파싱하여 처리하는 것이 더 간단하고 효율적일 수 있습니다.
    # 아래 코드는 서버에서 객체를 찾아 전달하는 예시입니다.
    initial_selected_categories_for_ui = []
    if selected_slug_list:
        # Category.objects.filter(slug__in=selected_slug_list) 로 가져오면 순서가 보장되지 않을 수 있으므로,
        # 슬러그 목록 순서대로 객체를 가져오려면 추가 로직이 필요하거나, JS에서 슬러그만 사용합니다.
        # 여기서는 간단히 필터링된 객체들을 전달합니다.
        initial_selected_categories_for_ui = list(Category.objects.filter(slug__in=selected_slug_list))


    context = {
        'posts': posts,
        'major_categories': major_categories_list,
        'initial_selected_categories_for_ui': initial_selected_categories_for_ui, # 초기 UI 표시용
        'current_category_slugs_str': selected_slugs_str, # JS 또는 페이지네이션 링크에 사용
        'search_type': search_type,
        'search_keyword': search_keyword,
    }
    return render(request, 'flo/study_post/study_post_list.html', context)

# 글 상세보기 (post_detail.html)
def study_post_detail(request, pk):
    # Post 객체를 가져올 때 categories도 prefetch_related로 가져옵니다.
    post = get_object_or_404(
        Post.objects.select_related('author').prefetch_related('comments__author', 'likes', 'categories'), # 'categories' 추가
        pk=pk
    )
    comments = post.comments.all() # 모델에서 정렬 순서 지정됨
    comment_form = CommentForm()

    # 조회수 증가 (세션 이용 중복 방지)
    session_key = f'post_viewed_{pk}'
    if not request.session.get(session_key, False):
        post.views += 1
        post.save(update_fields=['views'])
        request.session[session_key] = True

    is_liked = False
    if request.user.is_authenticated and post.likes.filter(pk=request.user.pk).exists():
        is_liked = True

    context = {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
        'is_liked': is_liked,
    }
    return render(request, 'flo/study_post/study_post_detail.html', context)

# 글쓰기 (post_form.html)
@login_required
def study_post_create(request):
    # ★★★ 최상위 대분류 목록을 major_categories 라는 이름으로 전달 ★★★
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES or None)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save() # 먼저 주 객체 저장
            form.save_m2m() # 그 다음 ManyToManyField 관계 저장
            messages.success(request, '게시글이 성공적으로 등록되었습니다.')
            return redirect(post.get_absolute_url())
    else:
        form = PostForm() # GET 요청 시 (또는 폼 유효성 실패 시)
    context = {
        'form': form,
        'form_title': '학습 게시판 글쓰기',
        'submit_text': '등록',
        'major_categories': major_categories_list, # ★★★ 컨텍스트 변수 이름 확인 ★★★
    }
    return render(request, 'flo/study_post/study_post_form.html', context)

def ajax_get_child_categories(request): # 함수 이름 확인!
    parent_id = request.GET.get('parent_id')
    children_data = []
    if parent_id:
        try:
            parent_category = Category.objects.get(id=parent_id)
            children = parent_category.children.all().order_by('name')
            for child in children:
                children_data.append({
                    'id': child.id,
                    'name': child.name,
                    'slug': child.slug, # 목록 페이지 필터링을 위해 slug 추가
                    'full_path': child.get_full_path_name, # Category 모델에 이 메서드가 있어야 함
                    'has_children': child.children.exists() # 하위 카테고리 존재 여부
                })
        except Category.DoesNotExist:
            # parent_id에 해당하는 카테고리가 없을 경우의 처리 (선택적)
            # 예를 들어, return JsonResponse({'error': 'Parent category not found.'}, status=404)
            pass # 그냥 빈 children_data 반환
        except Exception as e:
            # 기타 예외 처리 (선택적)
            # return JsonResponse({'error': str(e)}, status=500)
            pass
    return JsonResponse({'children': children_data})

# AJAX로 하위 카테고리 목록을 가져오는 뷰
def ajax_search_categories(request):
    query = request.GET.get('q', '')
    categories_data = []
    if query:
        # Q 객체를 사용하여 이름 또는 경로에 검색어가 포함된 모든 카테고리 검색
        # Category 모델에 get_full_path_name 같은 메서드가 있다고 가정
        # 실제로는 full_path 필드를 DB에 저장해두고 검색하는 것이 효율적일 수 있음
        matched_categories = Category.objects.filter(
            Q(name__icontains=query) | Q(slug__icontains=query) # 예시: 이름 또는 슬러그로 검색
            # 필요하다면 전체 경로(full_path)에 대해서도 검색
        ).distinct().order_by('name') # 중복 제거 및 정렬

        for cat in matched_categories:
            categories_data.append({
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug,
                'full_path': cat.get_full_path_name,
                'level': cat.get_level(), # Category 모델에 get_level() 메서드 필요
                'has_children': cat.children.exists()
            })
    return JsonResponse({'categories': categories_data})

# 글 수정 (post_form.html)
@login_required
def study_post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    # ★★★ 최상위 대분류 목록을 major_categories 라는 이름으로 전달 ★★★
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')

    if request.user != post.author:
        # ... (권한 오류 처리)
        messages.error(request, '수정 권한이 없습니다.')
        return redirect(post.get_absolute_url())

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES or None, instance=post)
        if form.is_valid():
            form.save() # instance가 있으면 save_m2m()도 보통 같이 처리됨
            messages.success(request, '게시글이 성공적으로 수정되었습니다.')
            return redirect(post.get_absolute_url())
    else:
        form = PostForm(instance=post)
    context = {
        'form': form,
        'post': post,
        'form_title': '학습 게시판 - 게시글 수정',
        'submit_text': '수정',
        'major_categories': major_categories_list, # ★★★ 컨텍스트 변수 이름 확인 ★★★
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


# 글 추천 (좋아요)
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
                return JsonResponse({
                    'status': 'success',
                    'comment_id': comment.id,
                    'author_username': comment.author.username, # 이미지에 username 표시
                    'content': comment.content,
                    'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'), # 형식 맞추기
                    'comment_count': post.comment_count,
                    # 프로필 이미지 URL 등 추가 정보 필요시 전달
                })
            messages.success(request, '댓글이 작성되었습니다.')
            return redirect(post.get_absolute_url() + f'#comment-{comment.id}') # 댓글 위치로 이동
    # GET 요청이거나 폼 유효성 실패 시 (보통 상세페이지에서 바로 처리)
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
            return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
        messages.error(request, '삭제 권한이 없습니다.')
        return redirect(post.get_absolute_url())


    if request.method == 'POST': # POST 요청으로만 삭제
        comment_id = comment.id
        comment.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'deleted_comment_id': comment_id, 'comment_count': post.comment_count})
        messages.success(request, '댓글이 삭제되었습니다.')
        return redirect(post.get_absolute_url())
    return HttpResponseBadRequest("잘못된 요청입니다.")


# FAQ 목록 (faq.html)
def faq_list(request):
    # FAQ 카테고리별로 그룹화해서 전달 (이미지 참고)
    faq_categories_with_items = FAQCategory.objects.prefetch_related('faq_items').all()
    # FAQ 페이지네이션은 이미지에 없으므로 일단 생략
    context = {
        'faq_categories_with_items': faq_categories_with_items,
    }
    return render(request, 'flo/faq/faq.html', context)