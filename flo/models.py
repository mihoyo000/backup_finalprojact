# flo/models.py
from datetime import timezone
from django.db import models
from django.conf import settings # settings.AUTH_USER_MODEL 사용
from django.urls import reverse
from django.db.models.signals import post_save # User 생성 시 Profile 자동 생성
from django.dispatch import receiver # User 생성 시 Profile 자동 생성
from django.utils.text import slugify

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
    slug = models.SlugField(max_length=50, unique=True, allow_unicode=True, help_text="URL에 사용될 이름", blank=True)
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
        verbose_name = "전체 카테고리"
        verbose_name_plural = "전체 카테고리 목록"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

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

    def is_leaf_node(self):
        return not self.children.exists()
    
    is_leaf_node.boolean = True

    def get_ancestors(self, include_self=False):
        path = []
        node = self
        if not include_self:
            node = self.parent

        while node:
            path.insert(0, node)
            node = node.parent
        return path

    def get_leaf_nodes(self):
        leaves = set()
        if not self.children.exists():
            leaves.add(self)
        else:
            for child in self.children.all().prefetch_related('children'):
                leaves.update(child.get_leaf_nodes())
        return list(leaves)

    def get_all_descendants(self, include_self=False):
        descendants = set()
        if include_self:
            descendants.add(self)

        children_qs = self.children.all().prefetch_related('children')
        for child in children_qs:
            descendants.add(child)
            descendants.update(child.get_all_descendants(include_self=False))
        return list(descendants)

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
        Category,
        related_name='posts',
        blank=True,
        verbose_name="카테고리(들)"
    )
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
    def calculated_comment_count(self):
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

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "FAQ 카테고리"
        verbose_name_plural = "FAQ 카테고리 목록"

class FAQItem(models.Model):
    category = models.ForeignKey(FAQCategory, on_delete=models.CASCADE, related_name='faq_items', verbose_name="FAQ 카테고리")
    question = models.CharField(max_length=255, verbose_name="질문")
    answer = models.TextField(verbose_name="답변")
    order = models.PositiveIntegerField(default=0, help_text="표시 순서 (낮을수록 먼저)")

    def __str__(self):
        return self.question

    class Meta:
        verbose_name = "FAQ 항목"
        verbose_name_plural = "FAQ 항목 목록"
        ordering = ['category', 'order', 'question']