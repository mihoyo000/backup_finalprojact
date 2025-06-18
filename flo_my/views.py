# flo_my/views.py

# --- 1. Python 기본 라이브러리 ---
import json
from datetime import timedelta

# --- 2. Django 핵심 라이브러리 ---
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import (
    Sum, Avg, Count, F, Q, When, Case,
    IntegerField, FloatField, DurationField, DateField, ExpressionWrapper
)
from django.db.models.functions import TruncDate, Cast, Extract

# --- 3. 외부 라이브러리 (Pandas) ---
import pandas as pd

# --- 4. 우리 앱의 모델과 폼 ---
from .models import LearningGoal
from .forms import LearningGoalForm, LearningGoalEditForm, IncorrectNoteSearchForm

# --- 5. 다른 앱의 모델 ---
from flo_exam.models import ExamDocument, UserExamSession, UserAnswer


# ======================================================================
# 마이페이지 뷰 함수들
# ======================================================================

@login_required
def mypage_dashboard_view(request):
    """마이페이지 대시보드를 렌더링합니다."""
    user = request.user
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6)
    three_days_later = today + timedelta(days=3)

    context = {
        'mypage_nav_active': 'dashboard',
    }

    # 학습 목표 달성률 계산
    goals_in_week = LearningGoal.objects.filter(user=user, created_at__date__range=[seven_days_ago, today])
    total_goals_count = goals_in_week.count()
    completed_goals_count = goals_in_week.filter(is_completed=True).count()
    context['achievement_rate'] = round((completed_goals_count / total_goals_count) * 100) if total_goals_count > 0 else 0
    context['total_goals_count'] = total_goals_count
    context['completed_goals_count'] = completed_goals_count

    # 최근 학습 활동
    context['recent_learning_activities'] = LearningGoal.objects.filter(user=user).order_by('-updated_at')[:4]

    # 마감 임박 학습 목표
    context['imminent_goals'] = LearningGoal.objects.filter(
        user=user,
        is_completed=False,
        due_date__range=[today, three_days_later]
    ).order_by('due_date')[:2]

    return render(request, 'flo_my/mypage/mypage_dashboard.html', context)


@login_required
def mypage_materials_view(request):
    """'나의 학습 자료' 목록을 보여주는 뷰입니다."""
    materials_query = ExamDocument.objects.filter(author=request.user).order_by('-is_important', '-uploaded_at')

    paginator = Paginator(materials_query, 4) # 페이지당 항목 수를 4개로 변경
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    num_pages = paginator.num_pages
    current_page = page_obj.number
    start_page = max(1, current_page - 2)
    end_page = min(num_pages, start_page + 4)
    if end_page - start_page < 4:
        start_page = max(1, end_page - 4)
    custom_page_range = range(start_page, end_page + 1)

    context = {
        'test_sets_page': page_obj,
        'custom_page_range': custom_page_range,
        'mypage_nav_active': 'materials',
    }
    return render(request, 'flo_my/mypage/mypage_materials.html', context)


@login_required
def mypage_incorrect_notes_view(request):
    """'나의 오답 노트' 목록을 보여주는 뷰입니다."""
    attempts_query = UserExamSession.objects.filter(user=request.user).select_related(
        'generated_exam__exam_document'
    ).order_by('-is_important', '-start_time')

    paginator = Paginator(attempts_query, 4) # 페이지당 항목 수를 4개로 변경
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    num_pages = paginator.num_pages
    current_page = page_obj.number
    start_page = max(1, current_page - 2)
    end_page = min(num_pages, start_page + 4)
    if end_page - start_page < 4:
        start_page = max(1, end_page - 4)
    custom_page_range = range(start_page, end_page + 1)

    context = {
        'attempts_page': page_obj,
        'custom_page_range': custom_page_range,
        'mypage_nav_active': 'incorrect_notes',
    }
    return render(request, 'flo_my/mypage/mypage_incorrect_notes.html', context)


@login_required
def mypage_learning_goals_view(request):
    """학습 목표 생성 및 목록을 보여주는 뷰입니다."""
    user = request.user

    if request.method == 'POST':
        form = LearningGoalForm(request.POST, user=user)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = user
            if not goal.title:
                if goal.goal_type == 'TEST_RETAKE' and goal.target_test_set:
                    goal.title = f"'{goal.target_test_set.title}' 다시 풀기"
                elif goal.goal_type == 'INCORRECT_ANSWERS_RETAKE' and goal.target_attempt_for_incorrect_notes:
                    exam_title = goal.target_attempt_for_incorrect_notes.generated_exam.exam_document.title
                    goal.title = f"'{exam_title}' 오답노트 학습"
            goal.save()
            messages.success(request, "새로운 학습 목표가 생성되었습니다.")
            return redirect('flo_my:mypage_learning_goals')
        else:
            messages.error(request, "입력 내용을 다시 확인해주세요.")
    else:
        form = LearningGoalForm(user=user)

    # --- ▼▼▼ 페이지네이션 및 정렬 로직 시작 ▼▼▼ ---
    # 1. 모든 진행중인 목표를 가져오되, 중요도 높은 순 -> 최신순으로 정렬
    all_goals_query = LearningGoal.objects.filter(
        user=user,
        is_completed=False
    ).order_by('-is_important', '-created_at')

    # 2. Paginator를 사용하여 4개씩 나누기
    paginator = Paginator(all_goals_query, 4)
    page_number = request.GET.get('page')
    learning_goals_page = paginator.get_page(page_number)

    # 3. 페이지네이션 범위 계산 (다른 페이지와 동일)
    num_pages = paginator.num_pages
    current_page = learning_goals_page.number
    start_page = max(1, current_page - 2)
    end_page = min(num_pages, start_page + 4)
    if end_page - start_page < 4:
        start_page = max(1, end_page - 4)
    custom_page_range = range(start_page, end_page + 1)
    # --- ▲▲▲ 로직 끝 ▲▲▲ ---

    context = {
        'form': form,
        'learning_goals_page': learning_goals_page, # 이제 페이지네이션된 객체를 전달
        'total_goals_count': all_goals_query.count(), # 필터링된 전체 목표 수
        'custom_page_range': custom_page_range, # 페이지네이션 범위 전달
        'mypage_nav_active': 'learning_goals',
    }
    return render(request, 'flo_my/mypage/learning_goals.html', context)


@login_required
def learning_goal_edit_view(request, goal_id):
    """학습 목표 수정 뷰입니다."""
    goal = get_object_or_404(LearningGoal, pk=goal_id, user=request.user)
    if request.method == 'POST':
        form = LearningGoalEditForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{goal.title}' 목표가 성공적으로 수정되었습니다.")
            return redirect('flo_my:mypage_learning_goals')
    else:
        form = LearningGoalEditForm(instance=goal)
    context = {
        'form': form,
        'goal': goal,
        'mypage_nav_active': 'learning_goals',
    }
    return render(request, 'flo_my/mypage/learning_goal_edit_form.html', context)


@login_required
@require_POST
def learning_goal_delete_view(request, goal_id):
    """학습 목표 삭제 뷰입니다."""
    goal = get_object_or_404(LearningGoal, pk=goal_id, user=request.user)
    goal_title = goal.title
    goal.delete()
    messages.success(request, f"'{goal_title}' 학습 목표가 삭제되었습니다.")
    return redirect('flo_my:mypage_learning_goals')


@login_required
def mypage_analytics_view(request):
    """
    학습 현황(Analytics) 페이지.
    Pandas를 활용하여 학습 데이터를 분석하고, Chart.js 시각화에 필요한 데이터를 가공합니다.
    """
    user = request.user
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=6)

    # --- 데이터가 없는 경우를 대비한 기본값 설정 ---
    chart_data = {
        'goal_flow': {'labels': [], 'data': []},
        'accuracy': {'labels': ['정답', '오답'], 'data': [0, 0]},
        'learning_time': {'labels': [], 'data': []},
    }
    strengths, weaknesses = [], []

    # --- 1. 목표 달성 플로우 (Line Chart) 데이터 ---
    completed_goals = LearningGoal.objects.filter(
        user=user, is_completed=True, updated_at__date__range=[seven_days_ago, today]
    ).values('updated_at')

    if completed_goals.exists():
        df_goals = pd.DataFrame(list(completed_goals))
        df_goals['date'] = pd.to_datetime(df_goals['updated_at']).dt.date
        goals_by_day = df_goals.groupby('date').size()

        # 7일간의 모든 날짜를 포함하도록 인덱스 재설정
        date_range = pd.date_range(start=seven_days_ago, end=today, freq='D').date
        goals_by_day = goals_by_day.reindex(date_range, fill_value=0)

        chart_data['goal_flow']['labels'] = [d.strftime('%m/%d') for d in goals_by_day.index]
        chart_data['goal_flow']['data'] = goals_by_day.values.tolist()


    # --- 2. 최근 정답률 분석 (Doughnut Chart) 데이터 ---
    recent_answers = UserAnswer.objects.filter(
        session__user=user,
        session__start_time__date__range=[seven_days_ago, today]
    ).values('is_correct')

    if recent_answers.exists():
        df_answers = pd.DataFrame(list(recent_answers))
        accuracy_counts = df_answers['is_correct'].value_counts()
        chart_data['accuracy']['data'] = [
            int(accuracy_counts.get(True, 0)),  # NumPy int64를 Python int로 변환
            int(accuracy_counts.get(False, 0))  # NumPy int64를 Python int로 변환
        ]

    # --- 3. 최근 학습 시간 (Bar Chart) 데이터 ---
    # 주석 처리 시작 ▼▼▼
    # recent_sessions = UserExamSession.objects.filter(
    #     user=user,
    #     ...
    # ).values('start_time', 'duration')
    #
    # if recent_sessions.exists():
    #     ...
    #     chart_data['learning_time']['data'] = (time_by_day / 60).round().astype(int).values.tolist()
    # 주석 처리 끝 ▲▲▲


    # --- 4. 나의 강점 & 약점 분석 (List) 데이터 ---
    all_sessions = UserExamSession.objects.filter(
        user=user, score__isnull=False
    ).values('generated_exam__exam_document__title', 'score')

    if all_sessions.exists():
        df_all_sessions = pd.DataFrame(list(all_sessions))
        # 필드 이름을 더 간단하게 변경
        df_all_sessions.rename(columns={'generated_exam__exam_document__title': 'title'}, inplace=True)

        # 시험지별 평균 점수 계산
        avg_scores = df_all_sessions.groupby('title')['score'].mean().round(1)

        strengths = avg_scores.nlargest(3).reset_index().to_dict('records')
        weaknesses = avg_scores.nsmallest(3).reset_index().to_dict('records')


    context = {
        'mypage_nav_active': 'analytics',
        # json.dumps를 사용해 파이썬 dict를 안전한 JSON 문자열로 변환
        'chart_data': json.dumps(chart_data),
        'strengths': strengths,
        'weaknesses': weaknesses,
    }

    return render(request, 'flo_my/mypage/mypage_analytics.html', context)


# ======================================================================
# AJAX 처리 뷰 함수들
# ======================================================================

@login_required
@require_POST
def ajax_toggle_material_importance(request, doc_id):
    """AJAX: 학습 자료(ExamDocument) 중요도 토글"""
    doc = get_object_or_404(ExamDocument, pk=doc_id, author=request.user)
    doc.is_important = not doc.is_important
    doc.save(update_fields=['is_important'])
    return JsonResponse({'status': 'success', 'is_important': doc.is_important})

@login_required
@require_POST
def ajax_delete_material(request, doc_id):
    """AJAX: 학습 자료(ExamDocument) 삭제"""
    doc = get_object_or_404(ExamDocument, pk=doc_id, author=request.user)
    doc.delete()
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def ajax_toggle_note_importance(request, attempt_id):
    """AJAX: 오답 노트(UserExamSession) 중요도 토글"""
    attempt = get_object_or_404(UserExamSession, pk=attempt_id, user=request.user)
    attempt.is_important = not attempt.is_important
    attempt.save(update_fields=['is_important'])
    return JsonResponse({'status': 'success', 'is_important': attempt.is_important})

@login_required
@require_POST
def ajax_delete_note(request, attempt_id):
    """AJAX: 오답 노트(UserExamSession) 삭제"""
    attempt = get_object_or_404(UserExamSession, pk=attempt_id, user=request.user)
    attempt.delete()
    return JsonResponse({'status': 'success'})

# ======================================================================
# 학습 목표 인라인 수정을 위한 AJAX 처리 뷰 함수들
# ======================================================================

@login_required
@require_POST
def ajax_toggle_learning_goal_importance(request, goal_id):
    """AJAX: 학습 목표 중요도 토글"""
    goal = get_object_or_404(LearningGoal, pk=goal_id, user=request.user)
    goal.is_important = not goal.is_important
    goal.save(update_fields=['is_important'])
    return JsonResponse({'status': 'success', 'is_important': goal.is_important})

@login_required
@require_POST
def ajax_update_learning_goal_title(request, goal_id):
    """AJAX: 학습 목표 제목 수정"""
    goal = get_object_or_404(LearningGoal, pk=goal_id, user=request.user)
    new_title = request.POST.get('title', '').strip()
    if new_title:
        goal.title = new_title
        goal.save(update_fields=['title'])
        return JsonResponse({'status': 'success', 'new_title': goal.title})
    return JsonResponse({'status': 'error', 'message': '제목을 비워둘 수 없습니다.'})

@login_required
@require_POST
def ajax_update_learning_goal_repetition_count(request, goal_id):
    """AJAX: 학습 목표 반복 횟수 수정"""
    goal = get_object_or_404(LearningGoal, pk=goal_id, user=request.user)
    try:
        new_count = int(request.POST.get('repetition_count', 1))
        if new_count >= goal.current_repetition_count and new_count > 0:
            goal.target_repetition_count = new_count
            goal.save() # save 메서드에서 is_completed와 achievement_rate가 자동 계산됨
            return JsonResponse({
                'status': 'success',
                'new_repetition_count': goal.target_repetition_count,
                'current_repetition_count': goal.current_repetition_count,
                'achievement_rate': goal.achievement_rate
            })
        else:
            return JsonResponse({'status': 'error', 'message': '목표 횟수는 현재 완료 횟수보다 크거나 같아야 합니다.'})
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': '유효한 숫자를 입력해주세요.'})

@login_required
@require_POST
def ajax_update_learning_goal_due_date(request, goal_id):
    """AJAX: 학습 목표 마감일 수정"""
    goal = get_object_or_404(LearningGoal, pk=goal_id, user=request.user)
    new_date_str = request.POST.get('due_date')

    if new_date_str:
        try:
            new_date = date.fromisoformat(new_date_str)
            today = timezone.now().date()

            # --- 백엔드 유효성 검사 추가 ---
            if new_date < today:
                return JsonResponse({'status': 'error', 'message': '마감일은 오늘 또는 미래의 날짜여야 합니다.'})

            goal.due_date = new_date
            goal.save(update_fields=['due_date'])
            return JsonResponse({'status': 'success', 'new_due_date': goal.due_date.strftime('%Y-%m-%d')})
        except ValueError:
            return JsonResponse({'status': 'error', 'message': '올바른 날짜 형식이 아닙니다.'})

    return JsonResponse({'status': 'error', 'message': '날짜를 입력해주세요.'})
