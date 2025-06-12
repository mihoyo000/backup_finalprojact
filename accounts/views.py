from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
# 인증/권한 관련
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.hashers import check_password
from django.contrib.auth.tokens import default_token_generator
# URL 처리/역참조
from django.urls import reverse
from django.conf import settings
# 폼/모델(프로젝트 내부)
from .forms import (
    SignUpForm,
    UserProfileBioForm,
    UserProfileInfoForm,
)
from .models import User  # 필요시 Terms, UserTermAgreement도 여기 추가
from accounts.models import JOB_CHOICES
# 이메일 발송 관련
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
# 유저 식별 인코딩
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


def send_verification_email(request):
    user_email = request.POST.get('new_email')
    
    # 유저 찾기(가입 직전이라면, DB에 없는 경우엔 임시로 만들 수도 있음)
    # 여기서는 예시로만 진행(유저 객체가 있다고 가정)
    user = request.user

    # 토큰 생성
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    # 인증 URL 생성 (domain은 settings.py나 request에서 가져와서 사용)
    domain = request.get_host()
    verify_url = f"http://{domain}{reverse('accounts:verify_email')}?uid={uid}&token={token}&email={user_email}"

    # 메일 본문 생성
    html_content = render_to_string(
        'postmail/signup_email_verify_template.html',
        {
            'verify_url': verify_url,  #용도 분할 필요섣 보임 0612
            'user_email': user_email,
            'user': user, 
        }
    )
    text_content = f'아래 링크를 눌러 이메일 인증을 완료하세요:\n{verify_url}\n\n감사합니다.'

    # 5. 메일 발송
    subject = '[FLO] 이메일 인증 안내'
    from_email = settings.DEFAULT_FROM_EMAIL
    msg = EmailMultiAlternatives(subject, text_content, from_email, [user_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    # 인증 플로우에 따라, 토큰 및 이메일을 DB/캐시/세션 등에 저장 필요
    request.session['pending_email'] = user_email
    return JsonResponse({'result': 'ok'})

from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator

User = get_user_model()

def verify_email(request):
    uidb64 = request.GET.get('uid')
    token = request.GET.get('token')
    new_email = request.GET.get('email')

    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # 이미 인증된 경우
    if user and getattr(user, 'email_verified', False):
        return redirect('accounts:email_already_verified')  # URL name

    # 토큰 검증
    if user is not None and default_token_generator.check_token(user, token):
        if new_email:
            user.email = new_email
            user.email_verified = True  # 상태값 True로
            user.save()
            return redirect('accounts:email_verified')
        else:
            # 이메일 없음
            return redirect('accounts:email_expired')
    else:
        # 토큰 만료/유효하지 않음
        return redirect('accounts:email_expired')



def login_view(request):
    if request.user.is_authenticated:
        return redirect('flo:home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, f'{user.username}님, 로그인되었습니다.')
            next_url = request.GET.get('next')
            return redirect(next_url or 'flo:home')
        else:
            messages.error(request, '아이디 또는 비밀번호가 올바르지 않습니다.')
    else:
        form = AuthenticationForm()
    return render(request, 'flo/auth/login.html', {'form': form, 'next': request.GET.get('next', '')})

#@login_required
def logout_view(request):
    if request.method == 'POST':
        username = request.user.username
        auth_logout(request)
        messages.info(request, f'{username}님, 성공적으로 로그아웃되었습니다.')
        return redirect('flo:home')
    return redirect('flo:home')

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)  # 회원가입 후 자동 로그인
            messages.success(request, '회원가입이 완료되었습니다.')

            return render(request, 'signup_landing/success.html', {
                'message': '회원가입이 완료되었습니다!',
                'redirect_url': 'flo:home'  # URL 패턴 이름으로 전달
            })
        else:
            messages.error(request, '입력하신 정보를 다시 확인해주세요.')
    else:
        form = SignUpForm()
    return render(request, 'sign_up.html', {'form': form})

def check_duplicate(request):
    field = request.GET.get('field')
    value = request.GET.get('value')
    
    if field == 'username':
        exists = User.objects.filter(username=value).exists()
        message = "이미 사용 중인 아이디입니다." if exists else "사용 가능한 아이디입니다."
    elif field == 'nickname':
        exists = User.objects.filter(nickname=value).exists()
        message = "이미 사용 중인 닉네임입니다." if exists else "사용 가능한 닉네임입니다."
    else:
        return JsonResponse({'error': '잘못된 필드명입니다.'}, status=400)
        
    return JsonResponse({
        'exists': exists,
        'message': message
    })

def email_pending_view(request):
    email = request.session.get('pending_email')
    return render(request, 'signup_landing/email_pending.html', {'pending_email': email})

def email_verified_view(request):
    return render(request, 'signup_landing/email_verified.html')

def email_already_verified_view(request):
    return render(request, 'signup_landing/email_already_verified.html')

def email_expired_view(request):
    return render(request, 'signup_landing/email_expired.html')

def activate_view(request, uidb64, token):
    # 이메일 인증 로직 구현
    pass

#임시 이메일 ui 확인 뷰
def ckmail_verify(request):
    return render(request, "postmail/signup_email_verify_template.html")

def ckmail_pass(request):
    return render(request, "postmail/flo_password_reset_email.html")

def ckmail_id(request):
    return render(request, "postmail/user_id_check.html")

#accounts-find
def find_id_view(request):
    return render(request, 'find_id.html')

def find_password_view(request):
    return render(request, 'find_password.html')

def find_password_pending_view(request):
    return render(request, 'find_password_email_pending.html')

def find_id_check_view(request):
    return render(request, 'find_id_check.html')

def password_change_view(request):
    return render(request, 'password_change.html')

#@login_required
def information_redi_view(request):
    """회원정보 수정 전 비밀번호 확인 페이지"""
    return render(request, 'information_redi.html')

#@login_required
def validate_password_for_edit_view(request):
    """회원정보 수정을 위한 비밀번호 검증"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        user = request.user
        
        if check_password(current_password, user.password):
            # 비밀번호가 일치하면 회원정보 수정 페이지로 리디렉션
            return redirect('accounts:edit_profile')  # 회원정보 수정 페이지 URL로 변경 필요
        else:
            messages.error(request, '비밀번호가 일치하지 않습니다.')
            return redirect('information_redi')
    
    return redirect('information_redi')

#@login_required
def user_setting_view(request):
    """회원정보 설정 페이지"""
    return render(request, 'user_setting.html', {
        'job_choices': JOB_CHOICES,
    })


@login_required
@require_POST
def update_marketing(request):      #알림설정 변경사항 저장용함수수
    user_terms = request.user.terms
    user_terms.agree_marketing = 'agree_marketing' in request.POST
    request.user.push_notifications = 'push_notifications' in request.POST
    request.user.activity_notifications = 'activity_notifications' in request.POST
    user_terms.save()
    request.user.save()

    return render(request, 'signup_landing/success.html', {
        'message': '변경사항 저장이 완료되었습니다.',
        'redirect_url': 'accounts:user_setting',
    })



@require_POST
@login_required
def update_profile(request):
    user = request.user
    profile = user.user_profile

    try:
        # 기본 이미지 리셋 요청일 경우: 다른 처리 생략하고 이미지만 변경
        if request.POST.get("reset_profile_image") == "true":
            if profile.profile_image:
                profile.profile_image.delete(save=False)
            profile.profile_image = None
            profile.save()

            theme_mode = request.session.get('theme_mode', 'light')
            default_img_url = f'/static/flo/images/icons/profile/default_profile_{theme_mode}.png'

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': '기본 이미지로 변경되었습니다.',
                    'new_image_url': default_img_url,
                    'has_custom_image': False
                })

            messages.success(request, '기본 이미지로 변경되었습니다.')
            return redirect('accounts:user_setting')

        # 기본 이미지 리셋이 아닌 경우: 전체 필드 업데이트 처리

        # 유저 필드 저장 (폼 외부 처리)
        user.nickname = request.POST.get("nickname", user.nickname)
        user.name = request.POST.get("name", user.name)
        user.save()

        # 프로필 이미지 업로드 처리
        if 'profile_image' in request.FILES:
            if profile.profile_image:
                profile.profile_image.delete(save=False)
            profile.profile_image = request.FILES['profile_image']
            profile.save()
            profile.refresh_from_db()
            new_image_url = profile.profile_image.url
        else:
            new_image_url = profile.profile_image.url if profile.profile_image else profile.get_profile_image_url

        # UserProfileBioForm 처리
        form = UserProfileBioForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': '프로필 정보가 성공적으로 변경되었습니다.',
                    'new_image_url': new_image_url,
                    'has_custom_image': bool(profile.profile_image)
                })

            messages.success(request, '프로필 정보가 성공적으로 변경되었습니다.')
            return redirect('accounts:user_setting')

        # 폼 검증 실패
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': '입력값을 다시 확인해주세요.',
                'errors': form.errors
            }, status=400)

        messages.error(request, '입력값을 다시 확인해주세요.')
        return redirect('accounts:user_setting')

    except Exception as e:
        import traceback
        print(f"Error in update_profile: {str(e)}")
        print(traceback.format_exc())

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f'프로필 업데이트 중 오류가 발생했습니다: {str(e)}'
            }, status=500)

        messages.error(request, f'프로필 업데이트 중 오류가 발생했습니다: {str(e)}')
        return redirect('accounts:user_setting')


@require_POST
@login_required
def update_info(request):           #인포용 변경사항 저장용 함수수
    user = request.user
    profile = user.user_profile

    # 1. User 필드 수동 저장
    user.nickname = request.POST.get("nickname", user.nickname)
    user.name = request.POST.get("name", user.name)
    user.save()

    # 2. UserProfile 필드 폼으로 저장 (바이오와 인포내용 폼 분리 0610)
    form = UserProfileInfoForm(request.POST, request.FILES, instance=profile)
    if form.is_valid():
        form.save()
        return render(request, 'signup_landing/success.html', {
            'message': '기본 정보가 성공적으로 변경되었습니다.',
            'redirect_url': 'accounts:user_setting',
        })
    else:
        return render(request, 'flo/user_setting.html', {
            'form': form,
            'message': '입력값을 다시 확인해주세요.',
        })


@login_required
def confirm_password_view(request):
    if request.method == 'POST':
        password = request.POST.get('current_password')
        user = request.user

        if user.check_password(password):
            return redirect('accounts:user_setting')  # 계정관리 URL name
        else:
            messages.error(request, '비밀번호가 일치하지 않습니다.')

    return render(request, 'information_redi.html')

