from django.contrib import admin
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('check-duplicate/', views.check_duplicate, name='check_duplicate'),
    path('logout/', views.logout_view, name='logout'),
    path('email-pending/', views.email_pending_view, name='email_pending'),
    path('email-verified/', views.email_verified_view, name='email_verified'),
    path('email-already-verified/', views.email_already_verified_view, name='email_already_verified'),
    path('email-expired/', views.email_expired_view, name='email_expired'),
    path('activate/<str:uidb64>/<str:token>/', views.activate_view, name='activate'),

    #임시 이메일 ui 확인
    path('ckmail_verify', views.ckmail_verify, name='ckmail_verify'),
    path('ckmail_pass', views.ckmail_pass, name='ckmail_pass'),
    path('ckmail_id', views.ckmail_id, name='ckmail_id'),

    path('find_id/', views.find_id_view, name='find_id'),
    path('find_password/', views.find_password_view, name='find_password'),
    path('find_password_pending/', views.find_password_pending_view, name='find_password_pending'),
    path('find_id_check/', views.find_id_check_view, name='find_id_check'),
    path('password_change/', views.password_change_view, name='password_change'),
    
    # 회원정보 본인 확인
    path('information_redi/', views.information_redi_view, name='information_redi'),
    path('confirm-password/', views.confirm_password_view, name='confirm_password'),
    
    # 회원정보 설정
    path('setting/', views.user_setting_view, name='user_setting'),
    # 변경값 저장
    path('settings/notifications/', views.update_marketing, name='update_marketing'),
    path('settings/profile/', views.update_profile, name='update_profile'),
    path('settings/info/', views.update_info, name='update_info'),

    #이메일 전송
    path('send_verification_email/', views.send_verification_email, name='send_verification_email'),
    path('verify_email/', views.verify_email, name='verify_email')

]