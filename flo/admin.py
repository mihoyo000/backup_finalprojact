# flo/admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Category, MajorCategory, MediumCategory, MinorCategory,
    Post, Attachment, Comment, FAQCategory, FAQItem,
    # --- 새로 추가된 모델들 임포트 ---
    UploadedPDF, TestSet, Question, Choice, 
    UserTestAttempt, UserAnswer, LearningGoal
)
from .forms import AttachmentForm # AttachmentForm 임포트

# --- 카테고리 관련 Admin 설정 (기존 코드 유지) ---
@admin.register(MajorCategory)
class MajorCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'display_children_count_for_major')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']
    exclude = ('parent',)
    def get_queryset(self, request): return super().get_queryset(request).filter(parent__isnull=True)
    def save_model(self, request, obj, form, change): obj.parent = None; super().save_model(request, obj, form, change)
    @admin.display(description='하위 카테고리(소분류) 수')
    def display_children_count_for_major(self, obj):
        try: actual_category = Category.objects.get(pk=obj.pk); return actual_category.children.count()
        except Category.DoesNotExist: return 0

@admin.register(MediumCategory)
class MediumCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent_name_display', 'children_count_display')
    search_fields = ('name', 'slug', 'parent__name')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('parent__name', 'name')
    fields = ('name', 'slug', 'parent')
    def get_queryset(self, request): major_category_ids = Category.objects.filter(parent__isnull=True).values_list('id', flat=True); return super().get_queryset(request).filter(parent_id__in=major_category_ids)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent": kwargs["queryset"] = Category.objects.filter(parent__isnull=True).order_by('name'); kwargs["empty_label"] = None; kwargs["help_text"] = "이 중분류가 속할 대분류를 선택하세요."
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    @admin.display(description='상위 카테고리 (대분류)', ordering='parent__name')
    def parent_name_display(self, obj): return obj.parent.name if obj.parent else "-"
    @admin.display(description='하위 카테고리 수')
    def children_count_display(self, obj):
        try: actual_category = Category.objects.get(pk=obj.pk); return actual_category.children.count()
        except Category.DoesNotExist: return 0

@admin.register(MinorCategory)
class MinorCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent_name_display_full_path')
    search_fields = ('name', 'slug', 'parent__name', 'parent__parent__name')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('parent__parent__name', 'parent__name', 'name')
    fields = ('name', 'slug', 'parent')
    def get_queryset(self, request): major_category_ids = Category.objects.filter(parent__isnull=True).values_list('id', flat=True); medium_category_ids = Category.objects.filter(parent_id__in=major_category_ids).values_list('id', flat=True); return super().get_queryset(request).filter(parent_id__in=medium_category_ids)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent": major_category_ids = Category.objects.filter(parent__isnull=True).values_list('id', flat=True); medium_categories_pks = Category.objects.filter(parent_id__in=major_category_ids).values_list('pk', flat=True); kwargs["queryset"] = Category.objects.filter(pk__in=medium_categories_pks).order_by('name'); kwargs["empty_label"] = None; kwargs["help_text"] = "이 소분류가 속할 중분류를 선택하세요."
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    @admin.display(description='상위 카테고리 (대분류 > 중분류)', ordering='parent__name')
    def parent_name_display_full_path(self, obj): return obj.parent.get_full_path_name if obj.parent else "-"

@admin.register(Category)
class OriginalCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent_name_for_original', 'get_level_display')
    search_fields = ('name',)
    ordering = ('name',)
    @admin.display(description='상위 카테고리')
    def parent_name_for_original(self, obj): return obj.parent.name if obj.parent else "최상위"
    @admin.display(description='레벨')
    def get_level_display(self, obj): return obj.get_level() if hasattr(obj, 'get_level') else '-'

# --- Attachment 및 Post Admin 설정 (기존 코드 유지, 약간의 정리) ---
@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'post_link', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('file__icontains', 'post__title__icontains') # 검색 필드 icontains 추가
    readonly_fields = ('uploaded_at',)
    def post_link(self, obj):
        if obj.post: link = reverse("admin:flo_post_change", args=[obj.post.id]); return format_html('<a href="{}">{}</a>', link, obj.post.title)
        return "-"
    post_link.short_description = "게시글"; post_link.admin_order_field = 'post__title'

class AttachmentInline(admin.TabularInline):
    model = Attachment
    form = AttachmentForm
    extra = 1
    readonly_fields = ('uploaded_at', 'filename_display')
    fields = ('file', 'filename_display', 'uploaded_at')
    def filename_display(self, obj): return obj.filename if obj.pk else "-"; filename_display.short_description = "파일명"

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'get_category_display_names_admin', 'author_username_display', 'created_at', 'is_notice') # author -> author_username_display
    list_filter = ('is_notice', 'categories', 'created_at', 'author')
    search_fields = ('title__icontains', 'content__icontains', 'author__username__icontains', 'categories__name__icontains') # 검색 필드 icontains 추가
    autocomplete_fields = ['author']
    filter_horizontal = ('categories', 'likes')
    inlines = [AttachmentInline]
    @admin.display(description='카테고리(들)')
    def get_category_display_names_admin(self, obj): return obj.get_category_display_names() if hasattr(obj, 'get_category_display_names') else "-"
    @admin.display(description='작성자', ordering='author__username') # 작성자 표시 개선
    def author_username_display(self, obj): return obj.author.username if obj.author else "-"

# --- CommentAdmin 설정 (기존 코드 유지, 약간의 정리) ---
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('post_title_link', 'author_username_display', 'content_excerpt', 'created_at_formatted')
    readonly_fields = ('author_link',) # post_title_link는 list_display에 있으므로 readonly_fields에서 제거 가능 (또는 유지)
    list_filter = ('created_at', 'author', 'post')
    search_fields = ('content__icontains', 'author__username__icontains', 'post__title__icontains', 'post__categories__name__icontains')
    autocomplete_fields = ['author', 'post']
    def post_title_link(self, obj):
        if obj.post: link = reverse("admin:flo_post_change", args=[obj.post.id]); return format_html('<a href="{}">{}</a>', link, obj.post.title)
        return "-"; post_title_link.short_description = "원본글 (링크)"; post_title_link.admin_order_field = 'post__title'
    @admin.display(description='작성자', ordering='author__username')
    def author_username_display(self, obj): return obj.author.username if obj.author else "-"
    def author_link(self, obj):
        if obj.author: link = reverse("admin:%s_%s_change" % (obj.author._meta.app_label, obj.author._meta.model_name), args=[obj.author.id]); return format_html('<a href="{}">{}</a>', link, obj.author.username)
        return "-"; author_link.short_description = "작성자 (링크)"
    @admin.display(description='댓글 내용 요약')
    def content_excerpt(self, obj): return (obj.content[:40] + '...') if len(obj.content) > 40 else obj.content
    @admin.display(description='작성일', ordering='created_at')
    def created_at_formatted(self, obj): return obj.created_at.strftime("%Y-%m-%d %H:%M")

# --- FAQ 관련 Admin 설정 (기존 코드 유지) ---
@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin): list_display = ('name',)
@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin): list_display = ('question', 'category', 'order'); list_filter = ('category',); search_fields = ('question', 'answer'); list_editable = ('order',)

# --- PDF 테스트 기능 및 학습 목표 관련 모델 Admin 등록 ---
@admin.register(UploadedPDF)
class UploadedPDFAdmin(admin.ModelAdmin):
    list_display = ('filename', 'user_username_display', 'uploaded_at')
    list_filter = ('user', 'uploaded_at')
    search_fields = ('filename', 'user__username')
    readonly_fields = ('uploaded_at', 'user', 'file', 'filename') # 생성 후 변경 안 되도록
    @admin.display(description='업로더', ordering='user__username')
    def user_username_display(self, obj): return obj.user.username if obj.user else "-"

@admin.register(TestSet)
class TestSetAdmin(admin.ModelAdmin):
    list_display = ('title', 'user_username_display', 'source_pdf_filename', 'num_questions_requested', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('title', 'user__username', 'source_pdf__filename')
    readonly_fields = ('created_at', 'user', 'source_pdf')
    @admin.display(description='생성자', ordering='user__username')
    def user_username_display(self, obj): return obj.user.username if obj.user else "-"
    @admin.display(description='원본 PDF', ordering='source_pdf__filename')
    def source_pdf_filename(self, obj): return obj.source_pdf.filename if obj.source_pdf else "-"

class ChoiceInline(admin.TabularInline): # Question 등록 시 Choice를 함께 관리
    model = Choice
    extra = 4 # 기본으로 4개의 보기 필드 표시
    max_num = 4 # 최대 4개까지만 (4지선다 가정)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('content_excerpt_admin', 'test_set_title', 'order', 'explanation_excerpt')
    list_filter = ('test_set__title',) # TestSet 제목으로 필터링
    search_fields = ('content', 'explanation', 'test_set__title')
    inlines = [ChoiceInline] # Question 추가/수정 페이지에 Choice 폼을 인라인으로
    list_editable = ('order',)
    ordering = ('test_set', 'order')
    @admin.display(description='문제 내용 (요약)')
    def content_excerpt_admin(self, obj): return (obj.content[:50] + '...') if len(obj.content) > 50 else obj.content
    @admin.display(description='시험 세트', ordering='test_set__title')
    def test_set_title(self, obj): return obj.test_set.title if obj.test_set else "-"
    @admin.display(description='해설 (요약)')
    def explanation_excerpt(self, obj): return (obj.explanation[:30] + '...') if obj.explanation and len(obj.explanation) > 30 else obj.explanation or "-"

# Choice 모델은 QuestionAdmin에서 인라인으로 관리하므로 별도 등록 생략 가능 (필요시 등록)
# @admin.register(Choice)
# class ChoiceAdmin(admin.ModelAdmin):
#     list_display = ('content', 'question_content_excerpt', 'is_correct')
#     list_filter = ('question__test_set__title', 'is_correct')
#     search_fields = ('content', 'question__content')
#     @admin.display(description='관련 문제 (요약)')
#     def question_content_excerpt(self, obj): return (obj.question.content[:30] + '...') if obj.question and len(obj.question.content) > 30 else (obj.question.content if obj.question else "-")

@admin.register(UserTestAttempt)
class UserTestAttemptAdmin(admin.ModelAdmin):
    list_display = ('user_username_display', 'test_set_title', 'score', 'started_at', 'completed_at_formatted','duration_seconds')
    list_filter = ('user', 'test_set__title', 'completed_at')
    search_fields = ('user__username', 'test_set__title')
    readonly_fields = ('user', 'test_set', 'started_at', 'completed_at', 'score', 'duration_seconds')
    @admin.display(description='응시자', ordering='user__username')
    def user_username_display(self, obj): return obj.user.username if obj.user else "-"
    @admin.display(description='응시 시험', ordering='test_set__title')
    def test_set_title(self, obj): return obj.test_set.title if obj.test_set else "-"
    @admin.display(description='완료 시간', ordering='completed_at')
    def completed_at_formatted(self, obj): return obj.completed_at.strftime("%Y-%m-%d %H:%M") if obj.completed_at else "-"

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt_summary', 'question_content_excerpt_ua', 'selected_answer_summary', 'is_correct')
    list_filter = ('attempt__user__username', 'attempt__test_set__title', 'is_correct')
    search_fields = ('attempt__user__username', 'question__content', 'selected_choice__content', 'input_answer')
    readonly_fields = ('attempt', 'question', 'selected_choice', 'input_answer', 'is_correct')
    @admin.display(description='응시 정보')
    def attempt_summary(self, obj): return f"{obj.attempt.user.username} - {obj.attempt.test_set.title[:20]}..." if obj.attempt else "-"
    @admin.display(description='질문 (요약)')
    def question_content_excerpt_ua(self, obj): return (obj.question.content[:30] + '...') if obj.question and len(obj.question.content) > 30 else (obj.question.content if obj.question else "-")
    @admin.display(description='선택/입력 답')
    def selected_answer_summary(self, obj): return obj.selected_choice.content[:30]+"..." if obj.selected_choice else (obj.input_answer[:30]+"..." if obj.input_answer else "답변 없음")

@admin.register(LearningGoal)
class LearningGoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'user_username_display', 'goal_type', 'due_date', 'achievement_rate_display', 'is_important', 'is_completed', 'created_at')
    list_filter = ('user', 'goal_type', 'is_important', 'is_completed', 'due_date')
    search_fields = ('title', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'achievement_rate_display') # is_completed는 save 메서드에서 관리
    list_editable = ('is_important', 'is_completed') # is_completed는 로직상 자동 변경되므로 editable에서 제외 고려
    fieldsets = (
        (None, {
            'fields': ('user', 'title', 'goal_type')
        }),
        ('목표 대상 (유형에 따라 하나만 선택)', { # 필드셋으로 그룹화
            'fields': ('target_test_set', 'target_attempt_for_incorrect_notes'),
            'description': "목표 유형에 맞는 대상 하나만 선택해주세요."
        }),
        ('목표 설정', {
            'fields': ('target_repetition_count', 'current_repetition_count', 'due_date', 'is_important', 'is_completed')
        }),
    )
    @admin.display(description='사용자', ordering='user__username')
    def user_username_display(self, obj): return obj.user.username if obj.user else "-"
    @admin.display(description='달성률', ordering='-id') # 정렬 기준은 적절히 변경
    def achievement_rate_display(self, obj): return f"{obj.achievement_rate}%"; achievement_rate_display.short_description = "달성률(%)"