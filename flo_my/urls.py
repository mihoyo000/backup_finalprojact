# flo_my/urls.py (최종 정리 버전)

from django.urls import path
from . import views

app_name = 'flo_my'

urlpatterns = [
    # ======================================================================
    # 1. 마이페이지 일반 페이지 경로
    # ======================================================================
    path('mypage/dashboard/', views.mypage_dashboard_view, name='mypage_dashboard'),
    path('mypage/analytics/', views.mypage_analytics_view, name='mypage_analytics'),
    path('mypage/materials/', views.mypage_materials_view, name='mypage_materials'),
    path('mypage/incorrect-notes/', views.mypage_incorrect_notes_view, name='mypage_incorrect_notes'),
    
    # 학습 목표 관련 페이지
    path('mypage/learning-goals/', views.mypage_learning_goals_view, name='mypage_learning_goals'),
    path('mypage/learning-goals/edit/<int:goal_id>/', views.learning_goal_edit_view, name='learning_goal_edit'),
    path('mypage/learning-goals/delete/<int:goal_id>/', views.learning_goal_delete_view, name='learning_goal_delete'),


    # ======================================================================
    # 2. AJAX 요청 처리 경로
    # ======================================================================
    
    # --- 학습 자료 (ExamDocument) 관련 AJAX ---
    path('ajax/material/toggle-importance/<int:doc_id>/', views.ajax_toggle_material_importance, name='ajax_toggle_material_importance'),
    path('ajax/material/delete/<int:doc_id>/', views.ajax_delete_material, name='ajax_delete_material'),

    # --- 오답 노트 (UserExamSession) 관련 AJAX ---
    path('ajax/note/toggle-importance/<int:attempt_id>/', views.ajax_toggle_note_importance, name='ajax_toggle_note_importance'),
    path('ajax/note/delete/<int:attempt_id>/', views.ajax_delete_note, name='ajax_delete_note'),
    path('ajax/learning-goal/toggle-importance/<int:goal_id>/', views.ajax_toggle_learning_goal_importance, name='ajax_toggle_learning_goal_importance'),
    path('ajax/learning-goal/update-title/<int:goal_id>/', views.ajax_update_learning_goal_title, name='ajax_update_learning_goal_title'),
    path('ajax/learning-goal/update-repetition-count/<int:goal_id>/', views.ajax_update_learning_goal_repetition_count, name='ajax_update_learning_goal_repetition_count'),
    path('ajax/learning-goal/update-due-date/<int:goal_id>/', views.ajax_update_learning_goal_due_date, name='ajax_update_learning_goal_due_date'),]