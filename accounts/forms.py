from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import MinLengthValidator, RegexValidator
from .models import User, UserTermAgreement, UserProfile, InterestTag

EMAIL_DOMAIN_CHOICES = [
    ('example.com', 'example.com'),
    ('gmail.com', 'gmail.com'),
    ('naver.com', 'naver.com'),
    ('daum.net', 'daum.net'),
    ('hanmail.net', 'hanmail.net'),
    ('nate.com', 'nate.com'),
    ('icloud.com', 'icloud.com'),
    ('me.com', 'me.com'),
    ('hotmail.com', 'hotmail.com'),
    ('outlook.com', 'outlook.com'),
    ('kakao.com', 'kakao.com'),
    ('yahoo.com', 'yahoo.com'),
]

class SignUpForm(UserCreationForm):
    email_id = forms.CharField(
        label='이메일 아이디',
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email_domain = forms.ChoiceField(
        label='이메일 도메인',
        choices=EMAIL_DOMAIN_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    username = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password1 = forms.CharField(
        label='비밀번호',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        validators=[
            MinLengthValidator(8, "비밀번호는 8자 이상이어야 합니다."),
            RegexValidator(
                regex='^(?=.*[A-Za-z])(?=.*\d).{8,}$',
                message='비밀번호는 영문자와 숫자를 포함해야 합니다.',
                code='invalid_password'
            )
        ]
    )
    password2 = forms.CharField(
        label='비밀번호 확인',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    name = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    nickname = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    agree_age_confirm = forms.BooleanField(required=True, label='만 14세 이상 여부 확인')
    agree_service = forms.BooleanField(required=True, label='서비스 이용약관 동의')
    agree_privacy = forms.BooleanField(required=True, label='개인정보 수집 및 이용 동의')
    agree_ai_data = forms.BooleanField(required=True, label='AI 학습용 데이터 수집 및 활용 동의')
    agree_marketing = forms.BooleanField(required=False, label='마케팅 정보 수신 동의')
    agree_outsourcing = forms.BooleanField(required=True, label='개인정보 처리위탁 동의')

    class Meta:
        model = User
        fields = ('username', 'name', 'nickname', 'password1', 'password2')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("비밀번호가 일치하지 않습니다.")
        return password2

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("이미 사용 중인 아이디입니다.")
        return username

    def clean_nickname(self):
        nickname = self.cleaned_data.get('nickname')
        if User.objects.filter(nickname=nickname).exists():
            raise forms.ValidationError("이미 사용 중인 닉네임입니다.")
        return nickname

    def clean(self):
        cleaned_data = super().clean()
        email_id = cleaned_data.get('email_id')
        email_domain = cleaned_data.get('email_domain')
        if email_id and email_domain:
            email = f"{email_id}@{email_domain}"
            cleaned_data['email'] = email
            if User.objects.filter(email=email).exists():
                self.add_error('email_id', '이미 사용 중인 이메일입니다.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data.get('email')
        if email:
            user.email = email
        if commit:
            user.save()
            UserTermAgreement.objects.create(
                user=user,
                agree_age_confirm=self.cleaned_data.get('agree_age_confirm'),
                agree_service=self.cleaned_data.get('agree_service'),
                agree_privacy=self.cleaned_data.get('agree_privacy'),
                agree_ai_data=self.cleaned_data.get('agree_ai_data'),
                agree_marketing=self.cleaned_data.get('agree_marketing'),
                agree_outsourcing=self.cleaned_data.get('agree_outsourcing'),
            )
        return user
    


class UserProfileBioForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['profile_bio']


class UserProfileInfoForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'birthday', 'gender', 'job', 'address']
        widgets = {
            'birthday': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].widget.attrs.update({'placeholder': '전화번호를 입력하세요'})
        self.fields['address'].widget.attrs.update({'placeholder': '주소를 입력하세요'})
