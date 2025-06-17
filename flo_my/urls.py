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
    path('ajax/note/delete/<int:attempt_id>/', views.ajax_delete_note, name='ajax_delete_note'),]
    
    # --- 학습 목표 (LearningGoal) 관련 AJAX ---
    # 참고: 현재 views.py에는 학습 목표 인라인 수정을 위한 AJAX 뷰가 없습니다.
    #      따라서 해당 기능이 필요할 때까지 아래 경로들은 주석 처리하는 것이 안전합니다.
    #      만약 인라인 수정 기능이 필요하다면, 이 주석을 풀고 views.py에 함수들을 추가해야 합니다.
    #
    # path('ajax/learning-goal/toggle-importance/<int:goal_id>/', views.ajax_toggle_learning_goal_importance, name='ajax_toggle_learning_goal_importance'),
    # path('ajax/learning-goal/update-title/<int:goal_id>/', views.ajax_update_learning_goal_title, name='ajax_update_learning_goal_title'),
    # path('ajax/learning-goal/update-repetition-count/<int:goal_id>/', views.ajax_update_learning_goal_repetition_count, name='ajax_update_learning_goal_repetition_count'),
    # path('ajax/learning-goal/update-due-date/<int:goal_id>/', views.ajax_update_learning_goal_due_date, name='ajax_update_learning_goal_due_date'),