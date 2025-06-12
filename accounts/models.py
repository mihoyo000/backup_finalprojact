from django.contrib.auth.models import AbstractUser, User
from django.db import models
from django.core.validators import MinLengthValidator, RegexValidator
from django.conf import settings

class User(AbstractUser):
    username = models.CharField(
        '아이디',
        max_length=20,
        unique=True,
        validators=[
            MinLengthValidator(4, "아이디는 4자 이상이어야 합니다."),
            RegexValidator(
                regex='^[a-zA-Z0-9]+$',
                message='아이디는 영문자와 숫자만 사용할 수 있습니다.',
                code='invalid_username'
            )
        ]
    )
    nickname = models.CharField(
        '닉네임',
        max_length=10,
        unique=True,
        validators=[
            MinLengthValidator(2, "닉네임은 2자 이상이어야 합니다."),
            RegexValidator(
                regex='^[가-힣a-zA-Z0-9]+$',
                message='닉네임은 한글, 영문자, 숫자만 사용할 수 있습니다.',
                code='invalid_nickname'
            )
        ]
    )
    name = models.CharField(
        '이름',
        max_length=10,
        validators=[
            MinLengthValidator(2, "이름은 2자 이상이어야 합니다."),
            RegexValidator(
                regex='^[가-힣a-zA-Z]+$',
                message='이름은 한글과 영문자만 사용할 수 있습니다.',
                code='invalid_name'
            )
        ]
    )
    email = models.EmailField('이메일', unique=True)

    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        related_name='custom_user_set',
        help_text='The groups this user belongs to.',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        related_name='custom_user_set',
        help_text='Specific permissions for this user.',
    )

    def __str__(self):
        return self.username

class UserTermAgreement(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='terms')

    agree_age_confirm = models.BooleanField()
    agree_service = models.BooleanField()
    agree_privacy = models.BooleanField()
    agree_ai_data = models.BooleanField()
    agree_marketing = models.BooleanField(default=False)
    agree_outsourcing = models.BooleanField()
    agreed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} 약관 동의"


# 성별 선택지
GENDER_CHOICES = [
    ('male', '남성'),
    ('female', '여성'),
    ('other', '기타'),
]

# 직업 선택지
JOB_CHOICES = [
    ('student', '학생'),
    ('developer', '개발자'),
    ('designer', '디자이너'),
    ('pm', '기획자'),
    ('etc', '기타'),
]

# 관심 분야 태그 (ManyToMany용)
class InterestTag(models.Model):
    name = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return self.name

# 사용자 프로필 (User 상속 구조)
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')
    profile_bio = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    birthday = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    job = models.CharField(max_length=20, choices=JOB_CHOICES, blank=True)
    address = models.CharField(max_length=255, blank=True)
    profile_image = models.ImageField(upload_to='profile/', blank=True, null=True)

    activity_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)

    interests = models.ManyToManyField(InterestTag, blank=True)

    def __str__(self):
        return f'{self.user.username}의 프로필'

    @property
    def get_profile_image_url(self):
        if self.profile_image:
            return self.profile_image.url

        theme_mode = getattr(settings, 'THEME_MODE', 'light')

        if theme_mode == 'dark':
            return '/static/flo/images/icons/profile/default_profile_dark.png'
        return '/static/flo/images/icons/profile/default_profile_light.png'

    @property
    def has_custom_profile_image(self):
        return bool(self.profile_image)
    
    
