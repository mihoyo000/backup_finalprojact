# flo/views.py
import os
from django.conf import settings # settings.STATIC_URL 사용을 위해 추가
from django.urls import reverse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Prefetch
from django.db.models.functions import Lower, Coalesce # ★★★ Lower, Coalesce 임포트 확인/추가 ★★★
from django.db.models import Value                     # ★★★ Value 임포트 확인/추가 (Coalesce와 함께 사용 시) ★★★
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.contrib import messages
from .models import Post, Attachment, Comment, Category, FAQCategory, FAQItem, Profile
from .forms import PostForm, AttachmentForm, CommentForm
from django.forms import inlineformset_factory

from django.core.serializers.json import DjangoJSONEncoder # 추가
import json # 추가

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
    AttachmentFormSet = inlineformset_factory(Post, Attachment, form=AttachmentForm, extra=1, can_delete=True)

    if request.method == 'POST':
        print("--- CREATE POST: POST request data ---") # 디버깅 추가
        print("REQUEST.POST:", request.POST)

        form = PostForm(request.POST, request.FILES)
        formset = AttachmentFormSet(request.POST, request.FILES, prefix='attachments')

        if form.is_valid() and formset.is_valid():
            print("--- CREATE POST: Form and Formset are VALID ---") # 디버깅 추가
            print("Form cleaned_data['categories']:", form.cleaned_data.get('categories')) # 디버깅 추가

            post = form.save(commit=False)
            post.author = request.user
            post.save()       # Post 객체 먼저 저장 (PK 생성)
            form.save_m2m()   # ★★★ ManyToManyField (categories) 저장 ★★★

            # formset.instance = post # formset에 Post 인스턴스 연결 (이미 save()에서 되었을 수도 있음)
            # formset.save()       # 첨부파일들 저장

            # formset 저장 부분 명시적으로 (이전 답변처럼)
            saved_attachments = formset.save(commit=False)
            for attachment in saved_attachments:
                attachment.post = post
                attachment.save()
            # 삭제 표시된 첨부파일 처리 (글쓰기 시에는 보통 없음)
            # for form_in_formset in formset.deleted_forms:
            #     if form_in_formset.instance.pk:
            #         form_in_formset.instance.delete()

            messages.success(request, '게시글이 성공적으로 등록되었습니다.')
            return redirect(post.get_absolute_url())
        else:
            print("--- CREATE POST: Form or Formset INVALID ---") # 디버깅 추가
            if not form.is_valid():
                print("PostForm errors:", form.errors.as_json(escape_html=True))
            if not formset.is_valid():
                print("AttachmentFormSet errors:")
                for i, fs_form_errors in enumerate(formset.errors):
                    if fs_form_errors:
                        print(f"  Form {i} errors: {fs_form_errors.as_json(escape_html=True)}")
                print(f"  AttachmentFormSet non_form_errors: {formset.non_form_errors().as_json(escape_html=True)}")
    else: # GET 요청
        form = PostForm()
        formset = AttachmentFormSet(prefix='attachments')
        initial_selected_categories_for_js = [] # 글쓰기 시에는 빈 배열

    # GET 요청 또는 POST 실패 시 컨텍스트
    # 글쓰기 시에는 initial_selected_categories_for_js가 비어있어야 함
    context = {
        'form': form,
        'formset': formset,
        'form_title': '학습 게시판 글쓰기',
        'submit_text': '등록',
        'major_categories': major_categories_list,
        'initial_selected_categories_for_js': json.dumps(initial_selected_categories_for_js if request.method == 'GET' else [], cls=DjangoJSONEncoder)
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
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')

    # Attachment 모델과 Post 모델을 연결하는 inlineformset_factory
    # Attachment 모델에 post 외래 키가 있고, related_name이 'post_attachments' (또는 기본값)라고 가정
    AttachmentFormSet = inlineformset_factory(
        Post,
        Attachment, # Attachment 모델 사용
        form=AttachmentForm, # AttachmentForm 사용
        fk_name='post', # Attachment 모델의 Post 외래 키 필드명
        extra=1, # 추가할 수 있는 빈 폼의 개수
        can_delete=True # 기존 첨부파일 삭제 기능 활성화
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
            
            # formset_is_valid가 True이거나, 개별 폼이 에러 없이 cleaned_data를 가질 수 있는 경우에만 접근
            # 또는 formset.is_bound 이고 fs_form.is_bound 일 때
            if formset.is_bound and fs_form.is_bound and not fs_form.errors: # 에러가 없는 경우 cleaned_data 접근 시도
                if 'DELETE' in fs_form.cleaned_data and fs_form.cleaned_data.get('DELETE'):
                    can_delete_checked = True
            elif 'DELETE' in fs_form.fields and fs_form.data.get(fs_form.prefix + '-DELETE'): # cleaned_data 접근 전, raw data 확인
                can_delete_checked = True


            print(f"  Form {i} instance in view: {fs_form.instance}, PK: {instance_pk_in_view}, Has Changed: {has_changed}, Is New: {is_new}, DELETE checked: {can_delete_checked}")
            if fs_form.errors:
                print(f"    Form {i} errors: {fs_form.errors.as_json(escape_html=True)}")


        if form_is_valid and formset_is_valid:
            saved_post = form.save()
            formset.save()
            messages.success(request, '게시글이 성공적으로 수정되었습니다.')
            return redirect(saved_post.get_absolute_url())
        else:
            if not form_is_valid: # PostForm 에러만 따로 출력
                print("--- PostForm errors on edit ---")
                print(form.errors.as_json(escape_html=True))
            if not formset_is_valid: # AttachmentFormSet 에러만 따로 출력
                print("--- AttachmentFormSet non_form_errors on edit ---")
                print(formset.non_form_errors().as_json(escape_html=True))
                # 개별 폼 에러는 위 루프에서 이미 출력됨
            messages.error(request, '게시글 수정에 실패했습니다. 입력 내용을 확인해주세요.')

    else: # GET 요청 (수정 폼을 처음 보여줄 때)
        form = PostForm(instance=post)
        
        existing_attachments_list = list(post.post_attachments.all()) # QuerySet을 리스트로 변환하여 수정 용이하게
        for attachment_instance in existing_attachments_list:
            if attachment_instance.file:
                # ★★★ 속성 이름을 '_display_filename'으로 변경 ★★★
                attachment_instance._display_filename = os.path.basename(attachment_instance.file.name)
            else:
                attachment_instance._display_filename = "파일 없음"

        formset = AttachmentFormSet(
            instance=post,
            prefix='attachments',
            # queryset 대신 initial 데이터로 전달하거나, 폼셋이 이 속성을 무시하도록 해야 할 수 있음
            # 여기서는 queryset을 사용하되, 템플릿에서 _display_filename을 사용
            queryset=Attachment.objects.filter(pk__in=[att.pk for att in existing_attachments_list]) # 원본 queryset 사용
        )
        
        # 폼셋의 각 폼에 _display_filename을 다시 설정 (queryset을 사용하면 인스턴스가 새로 로드될 수 있으므로)
        # 또는, initial 데이터로 전달하는 것이 더 안정적일 수 있습니다.
        # 아래는 formset.forms를 통해 접근하는 방법입니다.
        for i, form_in_formset in enumerate(formset.forms):
            if i < len(existing_attachments_list): # 기존 폼들에 대해서만
                form_in_formset.instance._display_filename = existing_attachments_list[i]._display_filename


    initial_selected_categories_for_js = []
    current_post_for_initial_data = form.instance if request.method == 'POST' and hasattr(form, 'instance') and form.instance.pk else post
    
    if current_post_for_initial_data and current_post_for_initial_data.pk:
        initial_selected_categories_for_js = [
            {'id': str(cat.id), 'name': cat.name, 'path': cat.get_full_path_name, 'slug': cat.slug}
            for cat in current_post_for_initial_data.categories.all()
        ]

    context = {
        'form': form,
        'formset': formset,
        'post': post,
        'form_title': '학습 게시판 - 게시글 수정',
        'submit_text': '수정',
        'major_categories': major_categories_list,
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
    # FAQ 카테고리별로 그룹화해서 전달 (이미지 참고)
    faq_categories_with_items = FAQCategory.objects.prefetch_related('faq_items').all()
    # FAQ 페이지네이션은 이미지에 없으므로 일단 생략
    context = {
        'faq_categories_with_items': faq_categories_with_items,
    }
    return render(request, 'flo/faq/faq.html', context)