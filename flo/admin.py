# board/admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Category, MajorCategory, MediumCategory, MinorCategory,
    Post, Attachment, Comment, FAQCategory, FAQItem
)
from .forms import AttachmentForm

# --- 대분류 관리자 ---
@admin.register(MajorCategory)
class MajorCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'display_children_count_for_major')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['name']
    exclude = ('parent',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(parent__isnull=True)

    def save_model(self, request, obj, form, change):
        obj.parent = None
        super().save_model(request, obj, form, change)

    @admin.display(description='하위 카테고리(소분류) 수')
    def display_children_count_for_major(self, obj):
        try:
            actual_category = Category.objects.get(pk=obj.pk)
            return actual_category.children.count()
        except Category.DoesNotExist:
            return 0

# --- 중분류 관리자 ---
@admin.register(MediumCategory)
class MediumCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent_name_display', 'children_count_display')
    search_fields = ('name', 'slug', 'parent__name')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('parent__name', 'name')
    fields = ('name', 'slug', 'parent')

    def get_queryset(self, request):
        major_category_ids = Category.objects.filter(parent__isnull=True).values_list('id', flat=True)
        return super().get_queryset(request).filter(parent_id__in=major_category_ids)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            kwargs["queryset"] = Category.objects.filter(parent__isnull=True).order_by('name')
            kwargs["empty_label"] = None
            kwargs["help_text"] = "이 중분류가 속할 대분류를 선택하세요."
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='상위 카테고리 (대분류)', ordering='parent__name')
    def parent_name_display(self, obj):
        if obj.parent:
            return obj.parent.name
        return "-"

    @admin.display(description='하위 카테고리 수')
    def children_count_display(self, obj):
        try:
            actual_category = Category.objects.get(pk=obj.pk)
            return actual_category.children.count()
        except Category.DoesNotExist:
            return 0

# --- 소분류 관리자 ---
@admin.register(MinorCategory)
class MinorCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent_name_display_full_path')
    search_fields = ('name', 'slug', 'parent__name', 'parent__parent__name')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('parent__parent__name', 'parent__name', 'name')
    fields = ('name', 'slug', 'parent')

    def get_queryset(self, request):
        major_category_ids = Category.objects.filter(parent__isnull=True).values_list('id', flat=True)
        medium_category_ids = Category.objects.filter(parent_id__in=major_category_ids).values_list('id', flat=True)
        return super().get_queryset(request).filter(parent_id__in=medium_category_ids)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            major_category_ids = Category.objects.filter(parent__isnull=True).values_list('id', flat=True)
            medium_categories_pks = Category.objects.filter(parent_id__in=major_category_ids).values_list('pk', flat=True)
            kwargs["queryset"] = Category.objects.filter(pk__in=medium_categories_pks).order_by('name')
            kwargs["empty_label"] = None
            kwargs["help_text"] = "이 소분류가 속할 중분류를 선택하세요."
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='상위 카테고리 (대분류 > 중분류)', ordering='parent__name')
    def parent_name_display_full_path(self, obj):
        if obj.parent:
            return obj.parent.get_full_path_name
        return "-"

# --- 원본 Category 모델 관리자 ---
@admin.register(Category)
class OriginalCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent_name_for_original', 'get_level_display')
    search_fields = ('name',)
    ordering = ('name',)

    @admin.display(description='상위 카테고리')
    def parent_name_for_original(self, obj):
        if obj.parent:
            return obj.parent.name
        return "최상위"
    
    @admin.display(description='레벨')
    def get_level_display(self, obj):
        if hasattr(obj, 'get_level'):
            return obj.get_level()
        return '-'

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'post_link', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('file', 'post__title')
    readonly_fields = ('uploaded_at',)

    def post_link(self, obj):
        if obj.post:
            link = reverse("admin:flo_post_change", args=[obj.post.id])
            return format_html('<a href="{}">{}</a>', link, obj.post.title)
        return "-"
    post_link.short_description = "게시글"
    post_link.admin_order_field = 'post__title'

class AttachmentInline(admin.TabularInline):
    model = Attachment
    form = AttachmentForm
    extra = 1
    readonly_fields = ('uploaded_at', 'filename_display')
    fields = ('file', 'filename_display', 'uploaded_at')

    def filename_display(self, obj):
        return obj.filename if obj.pk else "-"
    filename_display.short_description = "파일명"

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'get_category_display_names_admin', 'author', 'created_at', 'is_notice')
    list_filter = ('is_notice', 'categories', 'created_at', 'author')
    search_fields = ('title', 'content', 'author__username', 'categories__name')
    autocomplete_fields = ['author']
    filter_horizontal = ('categories', 'likes')
    inlines = [AttachmentInline]

    @admin.display(description='카테고리(들)')
    def get_category_display_names_admin(self, obj):
        if hasattr(obj, 'get_category_display_names'):
            return obj.get_category_display_names()
        return "-"

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('post_title_link', 'author_username_display', 'content_excerpt', 'created_at_formatted')
    readonly_fields = ('post_title_link', 'author_link')
    list_filter = ('created_at', 'author', 'post')
    search_fields = ('content', 'author__username', 'post__title', 'post__categories__name')
    autocomplete_fields = ['author', 'post']

    def post_title_link(self, obj):
        if obj.post:
            link = reverse("admin:flo_post_change", args=[obj.post.id])
            return format_html('<a href="{}">{}</a>', link, obj.post.title)
        return "-"
    post_title_link.short_description = "원본글 (링크)"
    post_title_link.admin_order_field = 'post__title'

    @admin.display(description='작성자', ordering='author__username')
    def author_username_display(self, obj):
        if obj.author:
            return obj.author.username
        return "-"

    def author_link(self, obj):
        if obj.author:
            link = reverse("admin:auth_user_change", args=[obj.author.id])
            return format_html('<a href="{}">{}</a>', link, obj.author.username)
        return "-"
    author_link.short_description = "작성자 (링크)"

    @admin.display(description='댓글 내용 요약')
    def content_excerpt(self, obj):
        return (obj.content[:40] + '...') if len(obj.content) > 40 else obj.content

    @admin.display(description='작성일', ordering='created_at')
    def created_at_formatted(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M")

@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'order')
    list_filter = ('category',)
    search_fields = ('question', 'answer')
    list_editable = ('order',)


