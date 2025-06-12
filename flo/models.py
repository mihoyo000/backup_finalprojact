# flo/models.py
from django.utils import timezone # timezone 임포트 수정 (datetime 대신)
from django.db import models
from django.conf import settings # settings.AUTH_USER_MODEL 사용
from django.urls import reverse
from django.db.models.signals import post_save # User 생성 시 Profile 자동 생성
from django.dispatch import receiver # User 생성 시 Profile 자동 생성
from django.core.exceptions import ValidationError


# --- 사용자 프로필 모델 추가 ---
class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="사용자")
    nickname = models.CharField(max_length=30, unique=True, blank=True, null=True, verbose_name="닉네임")
    profile_image = models.ImageField(upload_to='profile_pics/', blank=True, null=True, verbose_name="프로필 사진")

    def __str__(self):
        return f'{self.user.username} Profile'

    @property
    def get_display_name(self):
        return self.nickname if self.nickname else self.user.username

    @property
    def get_profile_image_url(self):
        if self.profile_image and self.profile_image.name:
            return self.profile_image.url
        # settings.STATIC_URL을 사용하려면 settings 임포트가 필요합니다 (이미 되어 있음).
        return settings.STATIC_URL + 'flo/images/icons/profile/default_profile_light.png'

    @property
    def has_custom_profile_image(self):
        return bool(self.profile_image and self.profile_image.name)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="카테고리명")
    slug = models.SlugField(max_length=50, unique=True, allow_unicode=True, help_text="URL에 사용될 이름")
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children', verbose_name="상위 카테고리"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "전체 카테고리"
        verbose_name_plural = "전체 카테고리 목록"
        ordering = ['name']

    def get_level(self):
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

class MajorCategory(Category):
    class Meta:
        proxy = True
        verbose_name = "학습 게시판 대분류"
        verbose_name_plural = "학습 게시판 대분류"

class MediumCategory(Category):
    class Meta:
        proxy = True
        verbose_name = "학습 게시판 중분류"
        verbose_name_plural = "학습 게시판 중분류"

class MinorCategory(Category):
    class Meta:
        proxy = True
        verbose_name = "학습 게시판 소분류"
        verbose_name_plural = "학습 게시판 소분류"

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_post_posts', verbose_name="작성자")
    categories = models.ManyToManyField(
        Category, related_name='posts', blank=True, verbose_name="카테고리(들)"
    )
    title = models.CharField(max_length=200, verbose_name="제목")
    content = models.TextField(verbose_name="내용") # 만약 TinyMCE를 Post 내용에도 사용하려면 HTMLField로 변경 고려
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="작성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    views = models.PositiveIntegerField(default=0, verbose_name="조회수")
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_study_post_posts', blank=True, verbose_name="추천수")
    is_notice = models.BooleanField(default=False, verbose_name="공지사항")
    # attached_file 필드는 Attachment 모델로 대체되었으므로 여기서는 제거하거나 주석 처리합니다.
    # attached_file = models.FileField(upload_to='attachments/', null=True, blank=True)

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
    
    def get_category_display_names(self):
        return ", ".join([cat.get_full_path_name for cat in self.categories.all()])
    
    @property
    def attachments_count(self):
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
        return self.file.name.split('/')[-1]

    @property
    def filename(self):
        return self.file.name.split('/')[-1]

    @property
    def download_filename(self):
        date_str = ""
        if self.uploaded_at:
            try:
                local_uploaded_at = timezone.localtime(self.uploaded_at)
                date_str = local_uploaded_at.strftime("%Y%m%d")
            except ValueError:
                date_str = self.uploaded_at.strftime("%Y%m%d")
            except AttributeError:
                pass
        original_filename = self.filename
        if date_str:
            return f"{date_str}_{original_filename}"
        else:
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
        ordering = ['created_at']

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

# --- PDF 테스트 기능 관련 모델 추가 ---
class UploadedPDF(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_pdfs', verbose_name="업로더")
    file = models.FileField(upload_to='pdfs/%Y/%m/%d/', verbose_name="PDF 파일") # 경로에 날짜 추가
    filename = models.CharField(max_length=255, verbose_name="원본 파일명")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="업로드 시간")
    # 추가 필드: 처리 상태 등
    # STATUS_CHOICES = [('pending', '대기중'), ('processing', '처리중'), ('completed', '완료'), ('failed', '실패')]
    # status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="처리 상태")

    def __str__(self):
        return f"{self.filename} (uploaded by {self.user.username})"

    class Meta:
        verbose_name = "업로드된 PDF"
        verbose_name_plural = "업로드된 PDF 목록"
        ordering = ['-uploaded_at']

class TestSet(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_sets', verbose_name="생성자")
    source_pdf = models.ForeignKey(UploadedPDF, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_tests', verbose_name="원본 PDF")
    title = models.CharField(max_length=255, default="생성된 시험", verbose_name="시험 제목")
    num_questions_requested = models.PositiveIntegerField(default=10, verbose_name="요청 문제 수") # 사용자가 요청한 문제 수
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성 시간")
    # 추가 필드: 실제 생성된 문제 수, 시험 설명 등
    # actual_num_questions = models.PositiveIntegerField(null=True, blank=True, verbose_name="실제 생성 문제 수")
    is_important = models.BooleanField(default=False, verbose_name="중요 표시") # ★★★ 추가된 필드 ★★★

    def __str__(self):
        return f"{self.title} (사용자: {self.user.username})"

    class Meta:
        verbose_name = "시험 세트"
        verbose_name_plural = "시험 세트 목록"
        ordering = ['-created_at']  


    def __str__(self):
        return f"{self.title} (for {self.user.username})"

    class Meta:
        verbose_name = "시험 세트"
        verbose_name_plural = "시험 세트 목록"
        ordering = ['-created_at']

class Question(models.Model):
    test_set = models.ForeignKey(TestSet, on_delete=models.CASCADE, related_name='questions', verbose_name="시험 세트")
    content = models.TextField(verbose_name="문제 내용") # 만약 TinyMCE 사용 시 from tinymce.models import HTMLField 필요
    # 정답 (객관식의 경우 정답 보기의 ID 또는 내용을 저장, 주관식은 모범 답안)
    # 이 필드는 Choice 모델을 사용한다면 필요 없을 수 있습니다. (Choice 모델의 is_correct로 판단)
    # correct_answer_text = models.TextField(null=True, blank=True, verbose_name="정답 텍스트(주관식/설명)")
    explanation = models.TextField(null=True, blank=True, verbose_name="해설")
    order = models.PositiveIntegerField(default=0, verbose_name="문제 순서")

    class Meta:
        verbose_name = "시험 문제"
        verbose_name_plural = "시험 문제 목록"
        ordering = ['test_set', 'order', 'id']

    def __str__(self):
        return f"Q{self.order or self.id}: {self.content[:50]}... (TestSet: {self.test_set_id})"

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices', verbose_name="관련 문제")
    content = models.CharField(max_length=500, verbose_name="보기 내용")
    is_correct = models.BooleanField(default=False, verbose_name="정답 여부")

    def __str__(self):
        return f"{self.content} (Correct: {self.is_correct})"

    class Meta:
        verbose_name = "객관식 보기"
        verbose_name_plural = "객관식 보기 목록"
        # ordering = ['question', 'id'] # 필요하다면 정렬 순서 지정

class UserTestAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_attempts', verbose_name="응시자")
    test_set = models.ForeignKey(TestSet, on_delete=models.CASCADE, related_name='attempts', verbose_name="응시 시험")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="시작 시간")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="완료 시간")
    score = models.FloatField(null=True, blank=True, verbose_name="점수") # 0.0 ~ 100.0 또는 총점
    is_important = models.BooleanField(default=False, verbose_name="중요 오답노트")
    duration_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name="응시 시간(초)")

    def __str__(self):
        score_display = f"{self.score:.1f}" if self.score is not None else "미완료"
        return f"Attempt by {self.user.username} on '{self.test_set.title}' (Score: {score_display})"

    class Meta:
        verbose_name = "사용자 시험 응시 기록"
        verbose_name_plural = "사용자 시험 응시 기록 목록"
        ordering = ['-started_at']

class UserAnswer(models.Model):
    attempt = models.ForeignKey(UserTestAttempt, on_delete=models.CASCADE, related_name='answers', verbose_name="응시 기록")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, verbose_name="질문")
    selected_choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="선택한 보기(객관식)")
    input_answer = models.TextField(null=True, blank=True, verbose_name="입력한 답(주관식)") # 주관식 답변용
    is_correct = models.BooleanField(null=True, blank=True, verbose_name="정답 여부") # 채점 후 결과

    def __str__(self):
        answer_display = self.selected_choice.content if self.selected_choice else self.input_answer or "답변 없음"
        return f"Answer to Q{self.question.id} by {self.attempt.user.username}: '{answer_display[:30]}...' (Correct: {self.is_correct})"

class Meta:
    verbose_name = "사용자 답변"
    verbose_name_plural = "사용자 답변 목록"
        # ordering = ['attempt', 'question']
    unique_together = ('attempt', 'question') # 한 응시에서 같은 문제에 대한 답변은 하나만 존재


    # 마이페이지 학습목표
class LearningGoal(models.Model):
    GOAL_TYPE_CHOICES = [
        ('TEST_RETAKE', 'Test 전체 다시 풀기'),
        ('INCORRECT_ANSWERS_RETAKE', '오답만 다시 풀기'),
        ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='learning_goals', verbose_name="사용자")
    title = models.CharField(max_length=255, verbose_name="학습 목표 제목")
    goal_type = models.CharField(max_length=30, choices=GOAL_TYPE_CHOICES, verbose_name="목표 유형")
        
        # Test 전체 다시 풀기 목표 시 사용
    target_test_set = models.ForeignKey(
            TestSet, 
            null=True, 
            blank=True, 
            on_delete=models.CASCADE, 
            related_name='learning_goals_for_test_retake', 
            verbose_name="대상 TestSet"
        )
        
        # 오답만 다시 풀기 목표 시 사용 (어떤 응시 기록의 오답인지)
    target_attempt_for_incorrect_notes = models.ForeignKey(
            UserTestAttempt, 
            null=True, 
            blank=True, 
            on_delete=models.CASCADE, 
            related_name='learning_goals_for_incorrect_retake', 
            verbose_name="오답노트 대상 응시기록"
        )

    target_repetition_count = models.PositiveIntegerField(default=1, verbose_name="목표 반복 학습 횟수")
    current_repetition_count = models.PositiveIntegerField(default=0, verbose_name="현재 완료 횟수")
        
    due_date = models.DateField(verbose_name="학습 마감일") # 뷰에서 일주일 단위로 설정되도록 제어
    is_important = models.BooleanField(default=False, verbose_name="중요 목표 여부 (최대 2개 선택 가능)")
    is_completed = models.BooleanField(default=False, verbose_name="목표 달성 여부")
        
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")

    def __str__(self):
            return f"{self.title} (사용자: {self.user.username})"

    @property
    def achievement_rate(self):
            if self.target_repetition_count > 0:
                rate = int((self.current_repetition_count / self.target_repetition_count) * 100)
                return min(rate, 100) # 100%를 넘지 않도록
            return 0

    @property
    def days_until_due(self):
            # 마감일까지 남은 일수 계산 (오늘 포함)
            # timezone.now().date()를 사용하기 위해 from django.utils import timezone 임포트 필요 (파일 상단에)
            today = timezone.now().date()
            delta = self.due_date - today
            if delta.days < 0:
                return "기한 지남" # 또는 음수 일수로 표시 (예: f"D{delta.days}")
            elif delta.days == 0:
                return "D-Day"
            else:
                return f"D-{delta.days}"

    def clean(self):
            super().clean() # 부모 클래스의 clean 메서드 호출
            # 목표 유형에 따라 target_test_set 또는 target_attempt_for_incorrect_notes 중 하나만 설정되도록 유효성 검사
            if self.goal_type == 'TEST_RETAKE' and not self.target_test_set:
                raise ValidationError({'target_test_set': 'Test 전체 다시 풀기 목표는 대상 TestSet을 지정해야 합니다.'})
            if self.goal_type == 'INCORRECT_ANSWERS_RETAKE' and not self.target_attempt_for_incorrect_notes:
                raise ValidationError({'target_attempt_for_incorrect_notes': '오답만 다시 풀기 목표는 대상 응시기록을 지정해야 합니다.'})
            
            # 두 필드가 동시에 설정되는 것을 방지 (하나만 선택)
            if self.target_test_set and self.target_attempt_for_incorrect_notes:
                raise ValidationError('목표 대상은 TestSet 또는 응시기록 중 하나만 선택해야 합니다.')
            
            # goal_type이 설정되지 않은 경우도 방지 (선택 사항, CharField에 blank=False, null=False가 기본)
            if not self.goal_type:
                raise ValidationError({'goal_type': '목표 유형을 선택해야 합니다.'})

    def save(self, *args, **kwargs):
            # 저장 전 is_completed 상태 자동 업데이트
            if self.target_repetition_count > 0 and self.current_repetition_count >= self.target_repetition_count:
                self.is_completed = True
            else:
                self.is_completed = False
            super().save(*args, **kwargs)

    class Meta:
            verbose_name = "학습 목표"
            verbose_name_plural = "학습 목표 목록"
            ordering = ['-is_important', 'due_date', '-created_at'] # 중요 목표, 마감일 임박, 최신순 정렬
        