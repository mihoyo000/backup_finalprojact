# flo_my/urls.py
from django.urls import path
from . import views

app_name = 'flo_my' # flo_my 앱의 새로운 네임스페이스 설정

urlpatterns = [
    # PDF 파일 업로드 및 문제 생성
    path('pdf/upload/', views.pdf_upload_view, name='pdf_upload'),
    path('pdf/<int:pdf_pk>/select_questions/', views.select_num_questions_view, name='select_num_questions'),

    # 시험 응시 및 결과
    path('test/<int:test_set_pk>/take/', views.take_test_view, name='take_test'), 
    path('test/result/<int:attempt_pk>/', views.test_result_view, name='test_result'),
    path('attempt/<int:attempt_pk>/retake_incorrect/', views.retake_incorrect_answers_view, name='retake_incorrect_answers'),
    path('retake_result/', views.retake_result_view, name='retake_result'),

    # 마이페이지
    path('mypage/', views.mypage_dashboard_view, name='mypage_dashboard'),
    path('mypage/materials/', views.mypage_materials_view, name='mypage_materials'),
    path('mypage/materials/delete/<int:test_set_pk>/', views.delete_test_set_view, name='delete_test_set'),
    path('mypage/goals/', views.mypage_learning_goals_view, name='mypage_learning_goals'),
    path('mypage/goal/<int:goal_pk>/edit/', views.learning_goal_edit_view, name='learning_goal_edit'),
    path('mypage/goal/<int:goal_pk>/delete/', views.learning_goal_delete_view, name='learning_goal_delete'),
    path('mypage/incorrect-notes/', views.mypage_incorrect_notes_view, name='mypage_incorrect_notes'),
    
    # 마이페이지 AJAX
    path('ajax/toggle_importance/<int:test_set_pk>/', views.toggle_importance_view, name='ajax_toggle_importance'),
    path('ajax/get_test_set_details/<int:test_set_pk>/', views.get_test_set_details_api_view, name='ajax_get_test_set_details'),
    path('ajax/incorrect-notes/toggle-importance/<int:attempt_id>/', views.toggle_incorrect_note_importance_view, name='toggle_incorrect_note_importance'),
    path('ajax/incorrect-notes/delete/<int:attempt_id>/', views.delete_incorrect_note_view, name='delete_incorrect_note'),
    path('ajax/incorrect-notes/details/<int:attempt_id>/', views.get_incorrect_note_details_view, name='get_incorrect_note_details'),
    
    # 기타
    path('download_test_set_pdf/<int:test_set_pk>/', views.download_test_set_pdf_view, name='download_test_set_pdf'),
]