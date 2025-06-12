# flo/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count
from django.db.models.functions import Lower
from django.core.serializers.json import DjangoJSONEncoder
from django.conf import settings
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.contrib import messages
from django.forms import inlineformset_factory
from datetime import timedelta
from django.db.models import F, Sum

# 외부 라이브러리 임포트
import fitz  # PyMuPDF (PDF 텍스트 추출)
import json
import openai
from weasyprint import HTML  # WeasyPrint 임포트

# 모델 임포트
from .models import (
    Post, Attachment, Comment, Category, FAQCategory, FAQItem,
    UploadedPDF, TestSet, Question, Choice,
    UserTestAttempt, UserAnswer, LearningGoal
)

# 폼 임포트
from .forms import (
    PostForm, AttachmentForm, CommentForm, CustomUserCreationForm,
    PDFUploadForm, LearningGoalForm, TestSetSearchForm, IncorrectNoteSearchForm 
)

# OpenAI API 키 설정
if settings.OPENAI_API_KEY:
    openai.api_key = settings.OPENAI_API_KEY
else:
    # 키가 없어도 서버는 실행되도록 설정
    pass

# ======================================================================
# 인증 및 기본 뷰
# ======================================================================

def home_view_in_flo(request):
    return render(request, 'flo/index.html')

def signup_view(request):
    if request.user.is_authenticated:
        messages.info(request, "이미 로그인되어 있습니다.")
        return redirect('flo:home')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f'{user.username}님, 회원가입이 완료되었습니다. 환영합니다!')
            return redirect('flo:study_post_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'flo/auth/signup.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        messages.info(request, "이미 로그인되어 있습니다.")
        return redirect('flo:study_post_list')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, f'{user.username}님, 로그인되었습니다.')
            next_url = request.GET.get('next')
            return redirect(next_url or 'flo:study_post_list')
        else:
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
        return redirect('flo:study_post_list')
    else:
        return redirect('flo:study_post_list')


# ======================================================================
# 게시판 (Study Post) 관련 뷰
# ======================================================================

def study_post_list(request):
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')
    selected_slugs_str = request.GET.get('category_slugs', '')
    selected_slug_list = [slug.strip() for slug in selected_slugs_str.split(',') if slug.strip()]
    post_query = Post.objects.select_related('author').prefetch_related('categories').annotate(
        num_comments=Count('comments', distinct=True),
        num_likes=Count('likes', distinct=True)
    ).order_by('-is_notice', '-created_at')
    if selected_slug_list:
        post_query = post_query.filter(categories__slug__in=selected_slug_list).distinct()
    search_type = request.GET.get('search_type', '')
    search_keyword = request.GET.get('search_keyword', '')
    if search_keyword:
        if search_type == 'title_content':
            post_query = post_query.filter(Q(title__icontains=search_keyword) | Q(content__icontains=search_keyword))
        elif search_type == 'title':
            post_query = post_query.filter(title__icontains=search_keyword)
        elif search_type == 'author':
            post_query = post_query.filter(author__username__icontains=search_keyword)
        elif search_type == 'category_name':
            post_query = post_query.filter(categories__name__icontains=search_keyword).distinct()
    paginator = Paginator(post_query, 10)
    page_number = request.GET.get('page')
    posts = paginator.get_page(page_number)
    initial_selected_categories_for_ui = []
    if selected_slug_list:
        initial_selected_categories_for_ui = list(Category.objects.filter(slug__in=selected_slug_list))
    context = {
        'posts': posts,
        'major_categories': major_categories_list,
        'initial_selected_categories_for_ui': initial_selected_categories_for_ui,
        'current_category_slugs_str': selected_slugs_str,
        'search_type': search_type,
        'search_keyword': search_keyword,
    }
    return render(request, 'flo/study_post/study_post_list.html', context)

def study_post_detail(request, pk):
    post = get_object_or_404(
        Post.objects.select_related('author').prefetch_related('comments__author', 'likes', 'categories'),
        pk=pk
    )
    comments = post.comments.all()
    comment_form = CommentForm()
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

@login_required
def study_post_create(request):
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')
    AttachmentFormSet = inlineformset_factory(Post, Attachment, form=AttachmentForm, extra=1, can_delete=True)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        formset = AttachmentFormSet(request.POST, request.FILES, prefix='attachments')
        if form.is_valid() and formset.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()
            saved_attachments = formset.save(commit=False)
            for attachment in saved_attachments:
                attachment.post = post
                attachment.save()
            messages.success(request, '게시글이 성공적으로 등록되었습니다.')
            return redirect(post.get_absolute_url())
    else: 
        form = PostForm()
        formset = AttachmentFormSet(prefix='attachments')
    initial_selected_categories_for_js = []
    context = {
        'form': form,
        'formset': formset,
        'form_title': '학습 게시판 글쓰기',
        'submit_text': '등록',
        'major_categories': major_categories_list,
        'initial_selected_categories_for_js': json.dumps(initial_selected_categories_for_js if request.method == 'GET' else [], cls=DjangoJSONEncoder)
    }
    return render(request, 'flo/study_post/study_post_form.html', context)

@login_required
def study_post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    major_categories_list = Category.objects.filter(parent__isnull=True).order_by('name')
    AttachmentFormSet = inlineformset_factory(Post, Attachment, form=AttachmentForm, fk_name='post', extra=1, can_delete=True)
    if request.user != post.author:
        messages.error(request, '수정 권한이 없습니다.')
        return redirect(post.get_absolute_url())
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        formset = AttachmentFormSet(request.POST, request.FILES, instance=post, prefix='attachments', queryset=post.post_attachments.all())
        if form.is_valid() and formset.is_valid():
            saved_post = form.save()
            formset.save()
            messages.success(request, '게시글이 성공적으로 수정되었습니다.')
            return redirect(saved_post.get_absolute_url())
    else: 
        form = PostForm(instance=post)
        formset = AttachmentFormSet(instance=post, prefix='attachments', queryset=post.post_attachments.all())
    initial_selected_categories_for_js = []
    current_post_for_initial_data = post
    if request.method == 'POST' and hasattr(form, 'instance') and form.instance:
        current_post_for_initial_data = form.instance
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

@login_required
@require_POST
def study_post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user != post.author:
        messages.error(request, '삭제 권한이 없습니다.')
        return redirect(post.get_absolute_url())
    post.delete()
    messages.success(request, '게시글이 삭제되었습니다.')
    return redirect('flo:study_post_list')

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


# ======================================================================
# 게시판 댓글(Comment) 관련 뷰
# ======================================================================

@login_required
@require_POST
def study_post_comment_create(request, post_pk):
    post = get_object_or_404(Post, pk=post_pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success', 'comment_id': comment.id,
                'author_username': comment.author.username, 'content': comment.content,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
                'comment_count': post.comment_count,
            })
        messages.success(request, '댓글이 작성되었습니다.')
        return redirect(post.get_absolute_url() + f'#comment-{comment.id}')
    messages.error(request, '댓글 작성에 실패했습니다.')
    return redirect(post.get_absolute_url())

@login_required
@require_POST
def study_post_comment_edit(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if request.user != comment.author:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    form = CommentForm(request.POST, instance=comment)
    if form.is_valid():
        form.save()
        return JsonResponse({
            'status': 'success', 'content': comment.content,
            'updated_at': comment.updated_at.strftime('%Y-%m-%d %H:%M')
        })
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

@login_required
@require_POST
def study_post_comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    post = comment.post
    if request.user != comment.author:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
        messages.error(request, '삭제 권한이 없습니다.')
        return redirect(post.get_absolute_url())
    comment_id = comment.id
    comment.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'deleted_comment_id': comment_id, 'comment_count': post.comment_count})
    messages.success(request, '댓글이 삭제되었습니다.')
    return redirect(post.get_absolute_url())


# ======================================================================
# 카테고리 AJAX 뷰
# ======================================================================

def ajax_get_child_categories(request):
    parent_id = request.GET.get('parent_id')
    children_data = []
    if parent_id:
        try:
            parent_category = Category.objects.get(id=parent_id)
            children = parent_category.children.all().order_by('name')
            for child in children:
                children_data.append({
                    'id': child.id, 'name': child.name, 'slug': child.slug,
                    'full_path': child.get_full_path_name, 'has_children': child.children.exists()
                })
        except Category.DoesNotExist:
            pass
    return JsonResponse({'children': children_data})

def ajax_search_categories(request):
    query = request.GET.get('q', '').strip()
    page = request.GET.get('page', 1)
    ITEMS_PER_PAGE = 15
    categories_data = []
    if query:
        final_results_set = set()
        direct_matches = Category.objects.annotate(name_lower=Lower('name')).filter(name_lower__contains=query)
        for category in direct_matches:
            final_results_set.add(category)
            if category.get_level() == 1:
                for child in category.children.all().filter(children__isnull=True):
                    final_results_set.add(child)
            elif category.get_level() == 0:
                for medium_child in category.children.all().filter(children__isnull=False):
                    for minor_child in medium_child.children.all().filter(children__isnull=True):
                        final_results_set.add(minor_child)
        all_sorted_results = sorted(list(final_results_set), key=lambda cat: (cat.get_level(), cat.get_full_path_name))
        paginator = Paginator(all_sorted_results, ITEMS_PER_PAGE)
        results_page = paginator.get_page(page)
        for cat in results_page:
            categories_data.append({
                'id': cat.id, 'name': cat.name, 'slug': cat.slug, 'full_path': cat.get_full_path_name,
                'level': cat.get_level(), 'has_children': cat.children.exists()
            })
        has_next_page = results_page.has_next()
        return JsonResponse({
            'categories': categories_data, 'has_next_page': has_next_page,
            'total_results': paginator.count, 'current_page': int(page)
        })
    return JsonResponse({'categories': [], 'has_next_page': False, 'total_results': 0, 'current_page': 1})


# ======================================================================
# FAQ 뷰
# ======================================================================

def faq_list(request):
    faq_categories_with_items = FAQCategory.objects.prefetch_related('faq_items').all()
    context = {'faq_categories_with_items': faq_categories_with_items}
    return render(request, 'flo/faq/faq.html', context)


# ======================================================================
# PDF 업로드 및 시험 생성 관련 뷰
# ======================================================================

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        # 실제 운영 시에는 로깅 프레임워크 사용 (e.g., logging.error(...))
        print(f"Error extracting text from PDF: {e}")
    return text

def generate_questions_via_chatgpt(pdf_text, num_questions_requested):
    if not settings.OPENAI_API_KEY:
        print("OpenAI API Key is not set.")
        return None
    
    prompt_text = f"""
    주어진 텍스트를 기반으로, 다음 요구사항을 만족하는 객관식 4지선다형 문제 {num_questions_requested}개를 한국어로 생성해 주세요.
    각 문제는 반드시 다음 JSON 형식을 따라야 합니다. 다른 부가적인 설명이나 텍스트는 절대 포함하지 말고, 오직 JSON 객체들의 리스트로만 응답해주세요.

    요구하는 JSON 형식의 예시:
    [
      {{"question_text": "문제 내용입니다.", "choices": {{"A": "보기 A", "B": "보기 B", "C": "보기 C", "D": "보기 D"}}, "correct_answer_label": "A", "explanation": "이것은 해설입니다."}},
      {{"question_text": "다음 문제 내용입니다.", "choices": {{"A": "선택지 1", "B": "선택지 2", "C": "선택지 3", "D": "선택지 4"}}, "correct_answer_label": "C", "explanation": "이 문제에 대한 설명입니다."}}
    ]

    위 예시와 동일한 구조로, 요청한 문제 수만큼의 JSON 객체를 포함하는 리스트를 생성해주세요.
    각 필드의 값은 반드시 문자열이어야 합니다.

    --- 제공된 텍스트 ---
    {pdf_text[:3500]}
    --- 텍스트 끝 ---
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an AI assistant that generates quiz questions from text. Respond ONLY with a JSON list of questions, no other text."},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=2048, n=1, stop=None, temperature=0.7,
        )
        content_str = response.choices[0].message['content']
        
        # 응답에서 JSON 부분만 깔끔하게 추출
        json_start = content_str.find('[')
        json_end = content_str.rfind(']')
        if json_start != -1 and json_end != -1:
            json_data_str = content_str[json_start : json_end + 1]
            parsed_data = json.loads(json_data_str)
            if isinstance(parsed_data, list):
                # 유효성 검사 추가
                valid_questions = [
                    item for item in parsed_data if isinstance(item, dict) and
                    "question_text" in item and "choices" in item and "correct_answer_label" in item and "explanation" in item
                ]
                return valid_questions[:num_questions_requested]
        return []
    except (openai.APIError, json.JSONDecodeError, IndexError) as e:
        print(f"Error in generate_questions_via_chatgpt: {e}")
        return None

@login_required
def pdf_upload_view(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_pdf_instance = form.save(commit=False)
            uploaded_pdf_instance.user = request.user
            if 'file' in request.FILES:
                uploaded_pdf_instance.filename = request.FILES['file'].name
            uploaded_pdf_instance.save()
            messages.success(request, f"'{uploaded_pdf_instance.filename}' 파일이 성공적으로 업로드되었습니다. 문제 수를 선택해주세요.")
            return redirect('flo:select_num_questions', pdf_pk=uploaded_pdf_instance.pk)
    else:
        form = PDFUploadForm()
    return render(request, 'flo/pdf_upload.html', {'form': form})

@login_required
def select_num_questions_view(request, pdf_pk):
    uploaded_pdf = get_object_or_404(UploadedPDF, pk=pdf_pk, user=request.user)
    if request.method == 'POST':
        num_questions_str = request.POST.get('num_questions')
        if num_questions_str in ['5', '10', '20']:
            num_questions = int(num_questions_str)
            test_set = TestSet.objects.create(
                user=request.user, source_pdf=uploaded_pdf,
                title=f"{uploaded_pdf.filename} 기반 시험 (요청 {num_questions}문제)",
                num_questions_requested=num_questions
            )
            pdf_text_content = extract_text_from_pdf(uploaded_pdf.file.path)
            if not pdf_text_content:
                messages.error(request, "PDF 파일에서 텍스트를 추출하는 데 실패했습니다.")
                return redirect('flo:select_num_questions', pdf_pk=pdf_pk)
            generated_q_data_list = generate_questions_via_chatgpt(pdf_text_content, num_questions)
            if generated_q_data_list is None or not generated_q_data_list:
                messages.error(request, "시험 문제 생성에 실패했습니다. 잠시 후 다시 시도해주세요.")
                test_set.delete() # 실패 시 생성된 빈 TestSet 삭제
                return redirect('flo:select_num_questions', pdf_pk=pdf_pk)
            for order_idx, q_data in enumerate(generated_q_data_list, 1):
                new_question = Question.objects.create(
                    test_set=test_set, content=q_data.get("question_text", "문제 내용 없음"),
                    explanation=q_data.get("explanation", ""), order=order_idx
                )
                choices_data = q_data.get("choices", {})
                correct_label = q_data.get("correct_answer_label", "").upper()
                for label, choice_text in choices_data.items():
                    Choice.objects.create(
                        question=new_question, content=choice_text,
                        is_correct=(label.upper() == correct_label)
                    )
            messages.success(request, f"{len(generated_q_data_list)}개 문제가 성공적으로 생성되었습니다!")
            return redirect('flo:take_test', test_set_pk=test_set.pk)
        else:
            messages.error(request, "올바른 문제 수를 선택해주세요.")
    context = {'uploaded_pdf': uploaded_pdf, 'num_options': [5, 10, 20]}
    return render(request, 'flo/select_num_questions.html', context)


# ======================================================================
# 시험 응시 및 결과 뷰
# ======================================================================

@login_required
def take_test_view(request, test_set_pk):
    test_set = get_object_or_404(TestSet.objects.prefetch_related('questions__choices'), pk=test_set_pk)
    if request.method == 'POST':
        duration_seconds_str = request.POST.get('duration_seconds', '0')
        try:
            duration_seconds = int(duration_seconds_str)
        except (ValueError, TypeError):
            duration_seconds = 0 # 변환 실패 시 기본값 0

        # UserTestAttempt 생성 시 duration_seconds도 함께 전달
        attempt = UserTestAttempt.objects.create(
            user=request.user, 
            test_set=test_set,
            duration_seconds=duration_seconds # 값 전달
        )
        correct_answers_count = 0
        total_questions = test_set.questions.count()

        for question in test_set.questions.all():
            selected_choice_pk_str = request.POST.get(f'question_{question.pk}')
            user_answer_is_correct = False
            selected_choice_instance = None
            if selected_choice_pk_str:
                try:
                    selected_choice_instance = Choice.objects.get(pk=int(selected_choice_pk_str), question=question)
                    if selected_choice_instance.is_correct:
                        correct_answers_count += 1
                        user_answer_is_correct = True
                except (ValueError, Choice.DoesNotExist):
                    pass
            UserAnswer.objects.create(
                attempt=attempt, question=question,
                selected_choice=selected_choice_instance, is_correct=user_answer_is_correct
            )
        
        attempt.score = (correct_answers_count / total_questions) * 100 if total_questions > 0 else 0
        attempt.completed_at = timezone.now()
        attempt.save()

        # 학습 목표 진행률 업데이트 로직
        try:
            learning_goal = LearningGoal.objects.get(
                user=request.user, goal_type='TEST_RETAKE',
                target_test_set=test_set, is_completed=False
            )
            learning_goal.current_repetition_count += 1
            learning_goal.save()
            messages.info(request, f"'{learning_goal.title}' 학습 목표 진행도가 업데이트되었습니다!")
        except LearningGoal.DoesNotExist:
            pass
        except LearningGoal.MultipleObjectsReturned:
            goal_to_update = LearningGoal.objects.filter(
                user=request.user, goal_type='TEST_RETAKE',
                target_test_set=test_set, is_completed=False
            ).order_by('-created_at').first()
            if goal_to_update:
                goal_to_update.current_repetition_count += 1
                goal_to_update.save()
                messages.info(request, f"'{goal_to_update.title}' 학습 목표 진행도가 업데이트되었습니다! (중복 목표 발견)")

        messages.success(request, f"시험을 완료했습니다! 당신의 점수는 {attempt.score:.2f}점 입니다.")
        return redirect('flo:test_result', attempt_pk=attempt.pk)
    
    context = {
        'test_set': test_set,
        'questions': test_set.questions.all().prefetch_related('choices'),
    }
    return render(request, 'flo/take_test.html', context)

@login_required
def test_result_view(request, attempt_pk):
    attempt = get_object_or_404(UserTestAttempt.objects.select_related('test_set', 'user'), pk=attempt_pk, user=request.user)
    user_answers = UserAnswer.objects.filter(attempt=attempt).select_related('question', 'selected_choice').order_by('question__order')
    
    results_data = []
    for ua in user_answers:
        choices = Choice.objects.filter(question=ua.question).order_by('id')
        correct_choice = next((c for c in choices if c.is_correct), None)
        results_data.append({
            'question_content': ua.question.content,
            'question_explanation': ua.question.explanation,
            'choices': choices,
            'selected_choice_pk': ua.selected_choice.pk if ua.selected_choice else None,
            'correct_choice_pk': correct_choice.pk if correct_choice else None,
            'is_correct': ua.is_correct,
        })

    context = {'attempt': attempt, 'test_set': attempt.test_set, 'results_data': results_data}
    return render(request, 'flo/test_result.html', context)


# ======================================================================
# 마이페이지 뷰
# ======================================================================

@login_required
def mypage_dashboard_view(request):
    user = request.user
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6)
    three_days_later = today + timedelta(days=3)

    context = {}

    # --- 1. 학습 목표 달성률 ---
    goals_in_week = LearningGoal.objects.filter(user=user, created_at__date__range=[seven_days_ago, today])
    total_goals_count = goals_in_week.count()
    completed_goals_count = goals_in_week.filter(is_completed=True).count()
    
    achievement_rate = 0
    if total_goals_count > 0:
        achievement_rate = round((completed_goals_count / total_goals_count) * 100)
        
    context['achievement_rate'] = achievement_rate
    context['total_goals_count'] = total_goals_count
    context['completed_goals_count'] = completed_goals_count

    # --- 2. 최근 학습 활동 ---
    recent_learning_activities = LearningGoal.objects.filter(user=user).order_by('-updated_at')[:4]
    context['recent_learning_activities'] = recent_learning_activities

    # --- 3. 마감 임박 학습 목표 ---
    imminent_goals = LearningGoal.objects.filter(
        user=user,
        is_completed=False,
        due_date__range=[today, three_days_later]
    ).order_by('due_date')[:2]
    context['imminent_goals'] = imminent_goals

    # --- 4. 바로가기: 가장 많이 틀린 시험 (로직 수정) ---
    weakest_attempt = None
    recent_attempts = UserTestAttempt.objects.filter(
        user=user, 
        completed_at__date__range=[seven_days_ago, today]
    ).annotate(
        # is_correct=False인 UserAnswer의 개수를 직접 카운트
        incorrect_count=Count('answers', filter=Q(answers__is_correct=False))
    ).order_by('-incorrect_count', '-completed_at').first() # 틀린 개수 내림차순, 같으면 최신순

    # 틀린 문제가 1개 이상 있는 경우에만 버튼을 표시
    if recent_attempts and recent_attempts.incorrect_count > 0:
        weakest_attempt = recent_attempts

    context['weakest_attempt'] = weakest_attempt

    return render(request, 'flo/mypage/mypage_dashboard.html', context)

@login_required
def mypage_materials_view(request):
    user = request.user
    test_sets_query = TestSet.objects.filter(user=user).order_by('-created_at')
    form = TestSetSearchForm(request.GET or None)

    if form.is_valid():
        search_title = form.cleaned_data.get('search_title')
        date_start = form.cleaned_data.get('search_date_start')
        date_end = form.cleaned_data.get('search_date_end')
        show_important_only = form.cleaned_data.get('show_important_only')

        if search_title:
            test_sets_query = test_sets_query.filter(title__icontains=search_title)
        if date_start:
            test_sets_query = test_sets_query.filter(created_at__date__gte=date_start)
        if date_end:
            test_sets_query = test_sets_query.filter(created_at__date__lte=date_end)
        if show_important_only:
            test_sets_query = test_sets_query.filter(is_important=True)
    
    paginator = Paginator(test_sets_query, 10)
    test_sets_page = paginator.get_page(request.GET.get('page'))
    context = {'test_sets_page': test_sets_page, 'search_form': form}
    return render(request, 'flo/mypage/mypage_materials.html', context)

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# ★★★ 여기가 문제의 핵심이었던 '마이페이지 학습 목표' 뷰입니다. ★★★
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
@login_required
def mypage_learning_goals_view(request):
    user = request.user
    if request.method == 'POST':
        form = LearningGoalForm(request.POST, user=user)
        if form.is_valid():
            important_goals_count = LearningGoal.objects.filter(user=user, is_important=True, is_completed=False).count()
            if form.cleaned_data.get('is_important') and important_goals_count >= 2:
                messages.error(request, "중요 학습 목표는 최대 2개까지만 설정할 수 있습니다.")
            else:
                learning_goal = form.save(commit=False)
                learning_goal.user = user
                
                # 제목 자동 생성 로직
                if not form.cleaned_data.get('title'):
                    goal_type = form.cleaned_data.get('goal_type')
                    if goal_type == 'TEST_RETAKE' and form.cleaned_data.get('target_test_set'):
                        learning_goal.title = f"{form.cleaned_data.get('target_test_set').title} 전체 다시 풀기"
                    elif goal_type == 'INCORRECT_ANSWERS_RETAKE' and form.cleaned_data.get('target_attempt_for_incorrect_notes'):
                        test_title = form.cleaned_data.get('target_attempt_for_incorrect_notes').test_set.title
                        learning_goal.title = f"{test_title} 오답 다시 풀기"
                    else:
                        learning_goal.title = "나의 학습 목표" # 기본값
                
                learning_goal.save()
                messages.success(request, "새로운 학습 목표가 생성되었습니다.")
                return redirect('flo:mypage_learning_goals')
        else:
            messages.error(request, "입력 내용을 다시 확인해주세요.")
    else: # GET 요청
        form = LearningGoalForm(user=user)

    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    # ★★★ 핵심 수정 사항: is_completed=False 조건 추가! "진행 중인" 목표만 가져옵니다. ★★★
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
    learning_goals = LearningGoal.objects.filter(user=user, is_completed=False).order_by('-is_important', 'due_date')

    context = {
        'form': form,
        'learning_goals': learning_goals,
    }
    return render(request, 'flo/mypage/learning_goals.html', context)

@login_required
def learning_goal_edit_view(request, goal_pk):
    goal = get_object_or_404(LearningGoal, pk=goal_pk, user=request.user)
    if request.method == 'POST':
        form = LearningGoalForm(request.POST, instance=goal, user=request.user)
        if form.is_valid():
            is_currently_important = goal.is_important
            becomes_important = form.cleaned_data.get('is_important')
            important_goals_count_excluding_current = LearningGoal.objects.filter(
                user=request.user, is_important=True, is_completed=False
            ).exclude(pk=goal.pk).count()
            if becomes_important and not is_currently_important and important_goals_count_excluding_current >= 2:
                messages.error(request, "중요 학습 목표는 최대 2개까지만 설정할 수 있습니다.")
            else:
                updated_goal = form.save()
                messages.success(request, f"'{updated_goal.title}' 학습 목표가 성공적으로 수정되었습니다.")
                return redirect('flo:mypage_learning_goals')
        else:
            messages.error(request, "입력 내용을 다시 확인해주세요.")
    else: # GET
        form = LearningGoalForm(instance=goal, user=request.user)

    context = {
        'form': form, 'goal': goal,
        'form_title': '학습 목표 수정', 'submit_text': '수정 완료'
    }
    return render(request, 'flo/mypage/learning_goal_edit_form.html', context)

@login_required
@require_POST
def learning_goal_delete_view(request, goal_pk):
    goal = get_object_or_404(LearningGoal, pk=goal_pk, user=request.user)
    goal_title = goal.title
    goal.delete()
    messages.success(request, f"'{goal_title}' 학습 목표가 삭제되었습니다.")
    return redirect('flo:mypage_learning_goals')


# ======================================================================
# 오답노트 재응시 관련 뷰
# ======================================================================

@login_required
def retake_incorrect_answers_view(request, attempt_pk):
    original_attempt = get_object_or_404(UserTestAttempt.objects.select_related('test_set'), pk=attempt_pk, user=request.user)
    questions_to_retake = Question.objects.filter(useranswer__attempt=original_attempt, useranswer__is_correct=False).prefetch_related('choices').order_by('order')
    
    if not questions_to_retake.exists():
        messages.warning(request, "이 시험에서 다시 풀 오답이 없습니다.")
        return redirect('flo:mypage_learning_goals')

    current_learning_goal = LearningGoal.objects.filter(
        user=request.user, goal_type='INCORRECT_ANSWERS_RETAKE',
        target_attempt_for_incorrect_notes=original_attempt, is_completed=False
    ).order_by('-created_at').first()

    if request.method == 'POST':
        duration_seconds_str = request.POST.get('duration_seconds', '0')
        try:
            duration_seconds = int(duration_seconds_str)
        except (ValueError, TypeError):
            duration_seconds = 0
        
        duration_message = f"소요 시간: {duration_seconds // 60}분 {duration_seconds % 60}초"
        correct_answers_count_retake = 0
        submitted_answers_data = []

        for question in questions_to_retake:
            selected_choice_pk_str = request.POST.get(f'question_{question.pk}')
            is_correct_retake = False
            selected_choice_id = None
            if selected_choice_pk_str:
                try:
                    selected_choice = Choice.objects.get(pk=int(selected_choice_pk_str), question=question)
                    selected_choice_id = selected_choice.pk
                    if selected_choice.is_correct:
                        correct_answers_count_retake += 1
                        is_correct_retake = True
                except (ValueError, Choice.DoesNotExist):
                    pass
            submitted_answers_data.append({
                'question_id': question.pk, 'selected_choice_id': selected_choice_id, 'is_correct': is_correct_retake
            })
        
        score_retake = (correct_answers_count_retake / len(questions_to_retake)) * 100
        score_message = f"오답 다시 풀기 결과: {correct_answers_count_retake} / {len(questions_to_retake)} ({score_retake:.0f}점)"

        if current_learning_goal:
            current_learning_goal.current_repetition_count += 1
            current_learning_goal.save()
            messages.info(request, f"'{current_learning_goal.title}' 학습 목표 진행도가 업데이트되었습니다! {score_message}")
        else:
            messages.success(request, f"오답 다시 풀기를 완료했습니다. {score_message}")
        
        request.session['retake_results'] = {
            'original_attempt_pk': original_attempt.pk,
            'submitted_answers': submitted_answers_data,
            'score': score_retake,
            'total_questions': len(questions_to_retake),
            'correct_count': correct_answers_count_retake
        }
        return redirect('flo:retake_result')

    context = {
        'test_set_title': f"{original_attempt.test_set.title} - 오답 다시 풀기",
        'questions': questions_to_retake,
        'form_action_url': reverse('flo:retake_incorrect_answers', kwargs={'attempt_pk': original_attempt.pk})
    }
    return render(request, 'flo/retake_incorrect_test.html', context)

@login_required
def retake_result_view(request):
    retake_results_data = request.session.pop('retake_results', None)
    if not retake_results_data:
        messages.error(request, "결과를 표시할 수 없습니다. 다시 시도해주세요.")
        return redirect('flo:mypage_learning_goals')

    original_attempt = get_object_or_404(UserTestAttempt, pk=retake_results_data['original_attempt_pk'])
    
    results_for_template = []
    question_ids = [sa['question_id'] for sa in retake_results_data['submitted_answers']]
    questions = Question.objects.in_bulk(question_ids)
    choices = Choice.objects.filter(question_id__in=question_ids).order_by('id')
    
    choices_by_question = {}
    for choice in choices:
        choices_by_question.setdefault(choice.question_id, []).append(choice)

    for submitted_answer in retake_results_data['submitted_answers']:
        question = questions.get(submitted_answer['question_id'])
        if not question: continue
        
        question_choices = choices_by_question.get(question.id, [])
        correct_choice = next((c for c in question_choices if c.is_correct), None)
        
        results_for_template.append({
            'question_content': question.content, 'question_explanation': question.explanation,
            'choices': question_choices, 'selected_choice_pk': submitted_answer['selected_choice_id'],
            'correct_choice_pk': correct_choice.pk if correct_choice else None,
            'is_correct': submitted_answer['is_correct'],
        })

    context = {
        'test_set_title': f"{original_attempt.test_set.title} - 오답 다시 풀기 결과",
        'score': retake_results_data['score'],
        'total_questions': retake_results_data['total_questions'],
        'correct_count': retake_results_data['correct_count'],
        'results_data': results_for_template,
        'original_attempt_pk': original_attempt.pk
    }
    return render(request, 'flo/retake_result.html', context)


# ======================================================================
# 마이페이지 AJAX 및 기타 뷰
# ======================================================================

@login_required
@require_POST
def toggle_importance_view(request, test_set_pk):
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseForbidden("AJAX 요청만 허용됩니다.")
    try:
        test_set = get_object_or_404(TestSet, pk=test_set_pk, user=request.user)
        test_set.is_important = not test_set.is_important
        test_set.save(update_fields=['is_important'])
        return JsonResponse({
            'status': 'success', 'message': '중요도가 변경되었습니다.',
            'test_set_id': test_set.pk, 'is_important': test_set.is_important
        })
    except TestSet.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '해당 TestSet을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_test_set_details_api_view(request, test_set_pk):
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseForbidden("AJAX 요청만 허용됩니다.")
    try:
        test_set = get_object_or_404(TestSet, pk=test_set_pk, user=request.user)
        questions_data = []
        for question in test_set.questions.all().order_by('order').prefetch_related('choices'):
            choices_data = []
            correct_choice_id = None
            for choice in question.choices.all().order_by('id'):
                choices_data.append({'id': choice.pk, 'content': choice.content})
                if choice.is_correct:
                    correct_choice_id = choice.pk
            questions_data.append({
                'id': question.pk, 'content': question.content, 'explanation': question.explanation,
                'choices': choices_data, 'correct_choice_id': correct_choice_id, 'order': question.order
            })
        return JsonResponse({
            'status': 'success', 'test_set_title': test_set.title, 'questions': questions_data
        })
    except TestSet.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '해당 TestSet을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def download_test_set_pdf_view(request, test_set_pk):
    # --- 1. 디버깅 시작점 ---
    print("\n" + "="*20 + " PDF 다운로드 뷰 시작 " + "="*20)
    print(f"요청된 TestSet PK: {test_set_pk}")

    try:
        # --- 2. 데이터 가져오기 ---
        test_set = get_object_or_404(TestSet, pk=test_set_pk, user=request.user)
        print(f"성공적으로 TestSet '{test_set.title}'를 가져왔습니다.")
        
        questions_with_choices = []
        for question in test_set.questions.all().order_by('order').prefetch_related('choices'):
            choices_list_for_template = [
                {'content': choice.content, 'is_correct': choice.is_correct}
                for choice in question.choices.all().order_by('id')
            ]
            questions_with_choices.append({
                'order': question.order,
                'content': question.content,
                'explanation': question.explanation,
                'choices_list': choices_list_for_template,
            })
        print(f"총 {len(questions_with_choices)}개의 문제를 PDF 데이터로 준비했습니다.")

        context = {
            'test_set': test_set,
            'questions': questions_with_choices,
        }

        # --- 3. HTML 문자열 생성 ---
        html_string = render_to_string('flo/pdf/test_set_pdf_template.html', context)
        print("성공적으로 HTML 템플릿을 문자열로 렌더링했습니다.")
        # print("--- 렌더링된 HTML (일부) ---")
        # print(html_string[:500]) # 너무 길면 터미널이 복잡해지므로 일부만 출력
        # print("--------------------------")

        # --- 4. PDF 생성 (WeasyPrint 호출) ---
        print("WeasyPrint를 사용하여 PDF 생성을 시작합니다...")
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        pdf_file = html.write_pdf()
        print("성공적으로 PDF 파일을 생성했습니다!")

        # --- 5. HTTP 응답 생성 및 반환 ---
        response = HttpResponse(pdf_file, content_type='application/pdf')
        from urllib.parse import quote
        filename = f"{test_set.title.replace(' ', '_')}.pdf"
        response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{quote(filename)}'
        
        print(f"'{filename}' 이름으로 다운로드 응답을 반환합니다.")
        print("="*20 + " PDF 다운로드 뷰 정상 종료 " + "="*20 + "\n")
        return response

    except TestSet.DoesNotExist:
        messages.error(request, "해당 시험지를 찾을 수 없습니다.")
        return redirect('flo:mypage_materials') 
    
    # ★★★★★★★★★★★★★★★★ 가장 중요한 예외 처리 블록 ★★★★★★★★★★★★★★★★
    except Exception as e:
        # WeasyPrint 오류 등 다른 모든 예외를 여기서 잡습니다.
        print("\n" + "!"*20 + " PDF 생성 중 심각한 오류 발생! " + "!"*20)
        print(f"오류 유형: {type(e).__name__}")
        print(f"오류 메시지: {e}")
        import traceback
        traceback.print_exc() # 오류의 상세한 위치를 추적하여 출력
        print("!"*55 + "\n")
        
        messages.error(request, f"PDF 생성 중 오류가 발생했습니다: {e}")
        return redirect('flo:mypage_materials')

@login_required
@require_POST # 보안을 위해 POST 요청만 허용
def delete_test_set_view(request, test_set_pk):
    # 현재 로그인한 사용자의 TestSet만 삭제할 수 있도록 필터링
    try:
        test_set = TestSet.objects.get(pk=test_set_pk, user=request.user)
        test_set_title = test_set.title
        test_set.delete()
        
        # AJAX 요청에 대한 성공 응답
        return JsonResponse({'status': 'success', 'message': f"'{test_set_title}' 학습 자료가 삭제되었습니다."})

    except TestSet.DoesNotExist:
        # 다른 사용자의 자료를 삭제하려고 하거나, 이미 삭제된 자료일 경우
        return JsonResponse({'status': 'error', 'message': '삭제할 자료를 찾을 수 없거나 권한이 없습니다.'}, status=404)
    except Exception as e:
        # 기타 서버 오류
        return JsonResponse({'status': 'error', 'message': f'삭제 중 오류가 발생했습니다: {str(e)}'}, status=500)

# ======================================================================
# 마이페이지 - 오답노트 뷰 (신규 추가)
# ======================================================================

@login_required
def mypage_incorrect_notes_view(request):
    """ 1. 오답노트 목록 페이지 (메인) """
    user = request.user
    attempts_query = UserTestAttempt.objects.filter(user=user).select_related('test_set').order_by('-started_at')
    
    form = IncorrectNoteSearchForm(request.GET or None)
    if form.is_valid():
        search_title = form.cleaned_data.get('search_title')
        date_start = form.cleaned_data.get('search_date_start')
        date_end = form.cleaned_data.get('search_date_end')
        show_important_only = form.cleaned_data.get('show_important_only')

        if search_title:
            attempts_query = attempts_query.filter(test_set__title__icontains=search_title)
        if date_start:
            attempts_query = attempts_query.filter(started_at__date__gte=date_start)
        if date_end:
            attempts_query = attempts_query.filter(started_at__date__lte=date_end)
        if show_important_only:
            attempts_query = attempts_query.filter(is_important=True)
    
    paginator = Paginator(attempts_query, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'attempts_page': page_obj, 
        'search_form': form
    }
    return render(request, 'flo/mypage/mypage_incorrect_notes.html', context)

@login_required
@require_POST
def toggle_incorrect_note_importance_view(request, attempt_id):
    """ 2. 오답노트 중요 표시/해제 (AJAX) """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseForbidden("AJAX 요청만 허용됩니다.")
    
    try:
        attempt = get_object_or_404(UserTestAttempt, pk=attempt_id, user=request.user)
        attempt.is_important = not attempt.is_important
        attempt.save(update_fields=['is_important'])
        
        return JsonResponse({
            'status': 'success',
            'message': '중요도가 변경되었습니다.',
            'attempt_id': attempt.pk,
            'is_important': attempt.is_important
        })
    except UserTestAttempt.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '해당 오답 기록을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
def delete_incorrect_note_view(request, attempt_id):
    """ 3. 오답노트 삭제 (AJAX) """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseForbidden("AJAX 요청만 허용됩니다.")

    try:
        attempt = get_object_or_404(UserTestAttempt, pk=attempt_id, user=request.user)
        attempt_title = attempt.test_set.title
        attempt.delete()
        
        return JsonResponse({
            'status': 'success', 
            'message': f"'{attempt_title}' 오답 기록이 삭제되었습니다."
        })
    except UserTestAttempt.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '삭제할 오답 기록을 찾을 수 없거나 권한이 없습니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'삭제 중 오류가 발생했습니다: {str(e)}'}, status=500)

@login_required
def get_incorrect_note_details_view(request, attempt_id):
    """ 4. 오답노트 상세 내용 모달로 보기 (AJAX) """
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return HttpResponseForbidden("AJAX 요청만 허용됩니다.")

    try:
        attempt = get_object_or_404(
            UserTestAttempt.objects.select_related('test_set'),
            pk=attempt_id, 
            user=request.user
        )

        # 해당 시험에서 '틀린' 답만 가져오기
        incorrect_answers = UserAnswer.objects.filter(
            attempt=attempt, 
            is_correct=False
        ).select_related('question', 'selected_choice').order_by('question__order')

        # JSON으로 보낼 데이터 가공
        incorrect_answers_data = []
        for ua in incorrect_answers:
            # 각 문제의 모든 보기를 가져와야 정답을 표시할 수 있음
            all_choices = Choice.objects.filter(question=ua.question).order_by('id')
            choices_data = []
            for choice in all_choices:
                choices_data.append({
                    'id': choice.pk,
                    'content': choice.content,
                    'is_correct': choice.is_correct
                })
            
            incorrect_answers_data.append({
                'question_content': ua.question.content,
                'explanation': ua.question.explanation,
                'choices': choices_data,
                'selected_choice_id': ua.selected_choice.pk if ua.selected_choice else None,
            })
        
        return JsonResponse({
            'status': 'success',
            'attempt_title': f"{attempt.test_set.title} (응시일: {attempt.started_at.strftime('%Y-%m-%d')})",
            'incorrect_answers': incorrect_answers_data
        })

    except UserTestAttempt.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '해당 오답 기록을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'데이터를 불러오는 중 오류가 발생했습니다: {str(e)}'}, status=500)

@login_required
def retake_from_note_view(request, attempt_id):
    """ 5. 오답노트 기반으로 '다시 풀기' """
    # 기존 오답 다시 풀기 로직을 거의 그대로 재사용할 수 있음
    # URL만 다르므로, 기존 뷰를 호출하거나 로직을 복사/붙여넣기
    return retake_incorrect_answers_view(request, attempt_pk=attempt_id)

