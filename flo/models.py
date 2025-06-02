# flo/models.py
from datetime import timezone
from django.db import models
from django.conf import settings # settings.AUTH_USER_MODEL 사용
from django.urls import reverse
from django.db.models.signals import post_save # User 생성 시 Profile 자동 생성
from django.dispatch import receiver # User 생성 시 Profile 자동 생성

# --- 사용자 프로필 모델 추가 ---
class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="사용자")
    nickname = models.CharField(max_length=30, unique=True, blank=True, null=True, verbose_name="닉네임")
    profile_image = models.ImageField(upload_to='profile_pics/', blank=True, null=True, verbose_name="프로필 사진")
    # bio = models.TextField(blank=True, null=True, verbose_name="자기소개") # 필요하다면 추가

    def __str__(self):
        return f'{self.user.username} Profile'

    # 닉네임이 설정되지 않은 경우 username을 대신 사용
    @property
    def get_display_name(self):
        return self.nickname if self.nickname else self.user.username

    # 프로필 이미지가 없는 경우 기본 이미지 URL 반환 (default 설정으로도 가능하지만, 명시적으로)
    @property
    def get_profile_image_url(self):
        if self.profile_image and self.profile_image.name:
            return self.profile_image.url # 사용자가 업로드한 이미지
        # 사용자가 업로드하지 않은 경우, 기본적으로 라이트 모드용 static 이미지를 반환
        return settings.STATIC_URL + 'flo/images/icons/profile/default_profile_light.png'

    @property
    def has_custom_profile_image(self):
        # 사용자가 직접 프로필 이미지를 업로드했는지 여부를 반환
        return bool(self.profile_image and self.profile_image.name)

# User 모델이 저장될 때 (특히 생성될 때) Profile 모델도 함께 생성/업데이트
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    try:
        instance.profile.save() # 기존 Profile이 있다면 저장 (업데이트 시그널 받을 수 있도록)
    except Profile.DoesNotExist: # 혹시 모를 Profile이 없는 경우 (데이터 마이그레이션 등으로 User는 있는데 Profile이 없을 때)
        Profile.objects.create(user=instance)

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="카테고리명")
    slug = models.SlugField(max_length=50, unique=True, allow_unicode=True, help_text="URL에 사용될 이름")
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
        verbose_name="상위 카테고리"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "전체 카테고리" # 모든 계층을 포함하는 원본
        verbose_name_plural = "전체 카테고리 목록"
        ordering = ['name']

    def get_level(self): # 계층 깊이 반환
        level = 0
        p = self.parent
        while p:
            level += 1
            p = p.parent
        return level

    @property
    def get_full_path_name(self):
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return " > ".join(path)

# --- 대분류 프록시 모델 ---
class MajorCategory(Category):
    class Meta:
        proxy = True
        verbose_name = "학습 게시판 대분류"
        verbose_name_plural = "학습 게시판 대분류" # 메뉴 이름

# --- 중분류 프록시 모델 ---
class MediumCategory(Category):
    class Meta:
        proxy = True
        verbose_name = "학습 게시판 중분류"
        verbose_name_plural = "학습 게시판 중분류" # 메뉴 이름

# --- 소분류 프록시 모델 ---
class MinorCategory(Category):
    class Meta:
        proxy = True
        verbose_name = "학습 게시판 소분류"
        verbose_name_plural = "학습 게시판 소분류" # 메뉴 이름

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_post_posts', verbose_name="작성자")
    # 기존 category 필드 주석 처리 또는 삭제
    # category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name='single_posts', verbose_name="카테고리")
    
    # 새로운 다중 카테고리 필드
    categories = models.ManyToManyField(
        Category,
        related_name='posts', # Category 모델에서 Post를 조회할 때 사용할 이름
        blank=True, # 카테고리 선택이 필수가 아니라면 True
        verbose_name="카테고리(들)"
    )
    # (만약 게시글에 대표 카테고리 개념이 필요하다면, 기존 ForeignKey를 유지하고 이름을 primary_category 등으로 변경할 수도 있습니다.)

    title = models.CharField(max_length=200, verbose_name="제목")
    content = models.TextField(verbose_name="내용")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="작성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    views = models.PositiveIntegerField(default=0, verbose_name="조회수")
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_study_post_posts', blank=True, verbose_name="추천수")
    is_notice = models.BooleanField(default=False, verbose_name="공지사항")
    attached_file = models.FileField(upload_to='attachments/', null=True, blank=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('flo:study_post_detail', args=[self.pk])

    @property
    def total_likes(self):
        return self.likes.count()

    @property
    def comment_count(self):
        return self.comments.count()
    
    def get_category_display_names(self): # 선택된 카테고리 이름들을 문자열로 반환 (템플릿 표시용)
        return ", ".join([cat.get_full_path_name for cat in self.categories.all()])
    
    @property
    def attachments_count(self): # 첨부파일 개수를 반환하는 프로퍼티
        return self.post_attachments.count()

    class Meta:
        verbose_name = "학습 게시글"
        verbose_name_plural = "학습 게시글 목록"
        ordering = ['-is_notice', '-created_at']
            
class Attachment(models.Model):
    post = models.ForeignKey(Post, related_name='post_attachments', on_delete=models.CASCADE, verbose_name="게시글")
    file = models.FileField(upload_to='post_attachments/%Y/%m/%d/', verbose_name="첨부파일")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="업로드 날짜")

    def __str__(self):
        # 파일 이름만 추출 (경로 제외)
        return self.file.name.split('/')[-1]

    @property
    def filename(self): # 템플릿에서 파일 이름만 쉽게 사용하기 위한 프로퍼티
        return self.file.name.split('/')[-1]

    # ★★★ 다운로드 시 사용할 파일명을 생성하는 프로퍼티 추가 ★★★
    @property
    def download_filename(self):
        # uploaded_at 필드를 사용하여 "YYYYMMDD_원래파일명" 형식으로 만듭니다.
        # self.uploaded_at이 naive datetime일 경우, settings.TIME_ZONE 기준으로 변환 필요 없음
        # (auto_now_add=True는 보통 aware datetime으로 저장)
        # 만약 naive datetime이고 시간대 변환이 필요하다면 추가 로직이 필요할 수 있습니다.
        # 여기서는 uploaded_at이 적절한 시간 정보를 가지고 있다고 가정합니다.
        
        date_str = ""
        if self.uploaded_at: # uploaded_at 값이 있는 경우에만 날짜 문자열 생성
            # Django의 TIME_ZONE 설정에 따라 aware datetime일 수 있습니다.
            # 만약 항상 특정 형식 (예: UTC 기준)으로 저장하고 싶다면 추가 처리 필요.
            # 여기서는 저장된 uploaded_at 값을 그대로 사용합니다.
            try:
                # timezone.localtime()을 사용하여 settings.TIME_ZONE 기준으로 변환 후 포맷팅 (더 안전)
                local_uploaded_at = timezone.localtime(self.uploaded_at)
                date_str = local_uploaded_at.strftime("%Y%m%d")
            except ValueError: # 만약 uploaded_at이 naive datetime이면 발생할 수 있음
                date_str = self.uploaded_at.strftime("%Y%m%d") # 이 경우 서버 시간대 기준
            except AttributeError: # uploaded_at이 None인 경우 등
                pass # date_str은 빈 문자열로 유지

        original_filename = self.filename # 기존 filename 프로퍼티 사용
        
        if date_str:
            return f"{date_str}_{original_filename}"
        else: # 날짜 정보가 없으면 원래 파일명 반환
            return original_filename

    class Meta:
        verbose_name = "첨부파일"
        verbose_name_plural = "첨부파일 목록"
        ordering = ['uploaded_at']

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments', verbose_name="원본글")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_post_comments', verbose_name="댓글 작성자")
    content = models.TextField(verbose_name="댓글 내용")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="댓글 작성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="댓글 수정일")

    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"

    class Meta:
        verbose_name = "댓글"
        verbose_name_plural = "댓글 목록"
        ordering = ['created_at'] # 오래된 댓글부터

class FAQCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="FAQ 카테고리명")
    def __str__(self): return self.name
    class Meta:
        verbose_name = "FAQ 카테고리"
        verbose_name_plural = "FAQ 카테고리 목록"

class FAQItem(models.Model):
    category = models.ForeignKey(FAQCategory, on_delete=models.CASCADE, related_name='faq_items', verbose_name="FAQ 카테고리")
    question = models.CharField(max_length=255, verbose_name="질문")
    answer = models.TextField(verbose_name="답변")
    order = models.PositiveIntegerField(default=0, help_text="표시 순서 (낮을수록 먼저)")
    def __str__(self): return self.question
    class Meta:
        verbose_name = "FAQ 항목"
        verbose_name_plural = "FAQ 항목 목록"
        ordering = ['category', 'order', 'question']