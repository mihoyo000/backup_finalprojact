# flo/models.py
from django.db import models
from django.conf import settings # settings.AUTH_USER_MODEL 사용
from django.urls import reverse

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


    class Meta:
        verbose_name = "학습 게시글"
        verbose_name_plural = "학습 게시글 목록"
        ordering = ['-is_notice', '-created_at']

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