# flo/urls.py
from django.urls import path
from . import views

app_name = 'flo' # 앱 네임스페이스 설정

urlpatterns = [
    path('', views.home_view_in_flo, name='home'),
    
    # 인증 관련 URL 추가
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # 학습 게시판
    path('study_post/list/', views.study_post_list, name='study_post_list'),
    path('category/<slug:category_slug>/', views.study_post_list, name='study_post_list_by_category'),
    path('ajax/search_categories/', views.ajax_search_categories, name='ajax_search_categories'),
    path('ajax/get_child_categories/', views.ajax_get_child_categories, name='ajax_get_child_categories'),
    path('study_post/new/', views.study_post_create, name='study_post_create'),
    path('study_post/<int:pk>/', views.study_post_detail, name='study_post_detail'),
    path('study_post/<int:pk>/edit/', views.study_post_edit, name='study_post_edit'),
    path('study_post/<int:pk>/delete/', views.study_post_delete, name='study_post_delete'),
    path('study_post/<int:pk>/like/', views.study_post_like, name='study_post_like'), # 추천

    # 댓글
    path('study_post/<int:post_pk>/comment/new/', views.study_post_comment_create, name='study_post_comment_create'),
    path('comment/<int:pk>/edit/', views.study_post_comment_edit, name='study_post_comment_edit'), # (선택적 AJAX)
    path('comment/<int:pk>/delete/', views.study_post_comment_delete, name='study_post_comment_delete'), # (선택적 AJAX)

    # FAQ
    path('faq/', views.faq_list, name='faq_list'),

    # PDF 파일 업로드
    path('pdf/upload/', views.pdf_upload_view, name='pdf_upload'),

    # PDF 파일에서 문제 생성
    path('pdf/<int:pdf_pk>/select_questions/', views.select_num_questions_view, name='select_num_questions'),

    # 시험 준비
    path('test/<int:test_set_pk>/take/', views.take_test_view, name='take_test'), 

    # 시험 결과
    path('test/result/<int:attempt_pk>/', views.test_result_view, name='test_result'),

    # 마이페이지
    path('mypage/', views.mypage_dashboard_view, name='mypage_dashboard'), # 대시보드
    path('mypage/materials/', views.mypage_materials_view, name='mypage_materials'), # 학습자료 (시험 목록) 페이지
    path('ajax/toggle_importance/<int:test_set_pk>/', views.toggle_importance_view, name='ajax_toggle_importance'),
    path('ajax/get_test_set_details/<int:test_set_pk>/', views.get_test_set_details_api_view, name='ajax_get_test_set_details'),
    path('download_test_set_pdf/<int:test_set_pk>/', views.download_test_set_pdf_view, name='download_test_set_pdf'),
    path('mypage/goals/', views.mypage_learning_goals_view, name='mypage_learning_goals'), # 학습 목표 목록 및 생성
    path('mypage/goal/<int:goal_pk>/edit/', views.learning_goal_edit_view, name='learning_goal_edit'), # 학습 목표 수정
    path('mypage/goal/<int:goal_pk>/delete/', views.learning_goal_delete_view, name='learning_goal_delete'), # 학습 목표 삭제
    path('mypage/incorrect-notes/', views.mypage_incorrect_notes_view, name='mypage_incorrect_notes'),
    path('mypage/incorrect-notes/toggle-importance/<int:attempt_id>/', views.toggle_incorrect_note_importance_view, name='toggle_incorrect_note_importance'),
    path('mypage/incorrect-notes/delete/<int:attempt_id>/', views.delete_incorrect_note_view, name='delete_incorrect_note'),
    path('mypage/incorrect-notes/details/<int:attempt_id>/', views.get_incorrect_note_details_view, name='get_incorrect_note_details'),
    path('mypage/incorrect-notes/retake/<int:attempt_id>/', views.retake_from_note_view, name='retake_from_note'),
    path('attempt/<int:attempt_pk>/retake_incorrect/', views.retake_incorrect_answers_view, name='retake_incorrect_answers'), # 오답노트 다시풀기
    path('retake_result/', views.retake_result_view, name='retake_result'), # 세션에서 데이터 가져오므로 별도 pk 필요 없을 수 있음
    path('materials/delete/<int:test_set_pk>/', views.delete_test_set_view, name='delete_test_set'),
]