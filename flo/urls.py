# flo/urls.py
from django.urls import path
from . import views

app_name = 'flo' # 앱 네임스페이스 설정

urlpatterns = [
    path('', views.home, name='home'),
    
    # 인증 관련 URL 추가
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
    path('study_post/<int:post_pk>/comments/', views.ajax_get_comments, name='ajax_get_comments'), # 댓글 AJAX 로드용 URL

    # FAQ
    path('faq/', views.faq_list, name='faq_list'),

    # Account URLs
    # path('accounts/signup/', views.signup_view, name='account_signup'), # /flo/accounts/signup/
    # path('accounts/login/', views.login_view, name='account_login'),   # /flo/accounts/login/
    # path('accounts/logout/', views.logout_view, name='account_logout'), # /flo/accounts/logout/
    # path('accounts/activate/<str:uidb64>/<str:token>/', views.activate_view, name='activate'), # /flo/accounts/activate/.../

    # # AJAX URLs (선택 사항)
    # path('ajax/check_username/', views.ajax_check_username, name='ajax_check_username'),
    # path('ajax/check_nickname/', views.ajax_check_nickname, name='ajax_check_nickname'),
    # path('ajax/resend_activation_email/', views.ajax_resend_activation_email, name='ajax_resend_activation_email'),
    
    # # --- 학습 게시판 URL 패턴 ---
    # path('study-board/', views.StudyPostListView.as_view(), name='study_post_list'),
    # path('study-board/post/new/', views.StudyPostCreateView.as_view(), name='study_post_create'),
    # path('study-board/post/<int:pk>/', views.StudyPostDetailView.as_view(), name='study_post_detail'),
    # path('study-board/post/<int:pk>/edit/', views.StudyPostUpdateView.as_view(), name='study_post_update'),
    # path('study-board/post/<int:pk>/delete/', views.StudyPostDeleteView.as_view(), name='study_post_delete'),
    
    # # 댓글 및 답글
    # path('study-board/post/<int:post_pk>/comment/add/', views.add_study_comment_or_reply, name='study_add_comment'),
    # path('study-board/post/<int:post_pk>/comment/<int:parent_comment_pk>/reply/add/', views.add_study_comment_or_reply, name='study_add_reply'),
    # path('study-board/comment/<int:comment_pk>/edit/', views.edit_study_comment, name='study_edit_comment'),
    # path('study-board/comment/<int:comment_pk>/delete/', views.delete_study_comment, name='study_delete_comment'),

    # 좋아요
    # path('study-board/post/<int:post_pk>/like/', views.toggle_study_post_like_view, name='study_toggle_like'),
]