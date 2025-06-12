# flo_my/admin.py
from django.contrib import admin
from .models import (
    UploadedPDF, TestSet, Question, Choice, 
    UserTestAttempt, UserAnswer, LearningGoal
)

# --- PDF 테스트 기능 및 학습 목표 관련 모델 Admin 등록 ---
@admin.register(UploadedPDF)
class UploadedPDFAdmin(admin.ModelAdmin):
    list_display = ('filename', 'user', 'uploaded_at')
    list_filter = ('user', 'uploaded_at')
    search_fields = ('filename', 'user__username')
    readonly_fields = ('uploaded_at', 'user', 'file', 'filename')

@admin.register(TestSet)
class TestSetAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'num_questions_requested', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('title', 'user__username')
    readonly_fields = ('created_at', 'user', 'source_pdf')

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    max_num = 4

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'test_set', 'order')
    list_filter = ('test_set__title',)
    search_fields = ('content', 'explanation', 'test_set__title')
    inlines = [ChoiceInline]
    list_editable = ('order',)
    ordering = ('test_set', 'order')

@admin.register(UserTestAttempt)
class UserTestAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'test_set', 'score', 'started_at', 'completed_at', 'duration_seconds')
    list_filter = ('user', 'test_set__title', 'completed_at')
    search_fields = ('user__username', 'test_set__title')
    readonly_fields = ('user', 'test_set', 'started_at', 'completed_at', 'score', 'duration_seconds')

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'selected_choice', 'is_correct')
    list_filter = ('attempt__user__username', 'attempt__test_set__title', 'is_correct')
    search_fields = ('attempt__user__username', 'question__content')
    readonly_fields = ('attempt', 'question', 'selected_choice', 'is_correct')

@admin.register(LearningGoal)
class LearningGoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'goal_type', 'due_date', 'achievement_rate', 'is_important', 'is_completed')
    list_filter = ('user', 'goal_type', 'is_important', 'is_completed', 'due_date')
    search_fields = ('title', 'user__username')
    readonly_fields = ('created_at', 'updated_at')