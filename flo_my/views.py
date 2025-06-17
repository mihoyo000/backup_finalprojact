# flo_my/views.py (최종 정리 버전)

# --- 1. Python 기본 라이브러리 ---
from datetime import timedelta, date
import json

# --- 2. Django 핵심 라이브러리 ---
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Avg, Count, F, When, Case, IntegerField, FloatField, Q
from django.db.models.functions import TruncDate
from django.views.decorators.http import require_POST
from django.contrib import messages

# --- 3. 외부 라이브러리 (Pandas) ---
# import pandas as pd # 아직 사용하지 않으므로 주석 처리

# --- 4. 우리 앱의 모델과 폼 ---
from .models import LearningGoal
# 모든 폼을 명시적으로 임포트합니다.
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
    
    paginator = Paginator(materials_query, 5)
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
    
    paginator = Paginator(attempts_query, 5)
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

    all_goals = LearningGoal.objects.filter(user=user, is_completed=False).order_by('-is_important', 'due_date')
    
    context = {
        'form': form, 
        'learning_goals_page': all_goals, # 템플릿 변수 이름을 일관성 있게 변경
        'total_goals_count': LearningGoal.objects.filter(user=user).count(), # '새 목표 추가' 버튼 표시용
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
    """학습 현황(Analytics) 페이지 뷰입니다."""
    # 지금은 비워두고, 나중에 데이터 분석 로직으로 채웁니다.
    context = {
        'mypage_nav_active': 'analytics',
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