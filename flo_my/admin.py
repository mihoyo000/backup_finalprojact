# flo_my/admin.py (정리 후)

from django.contrib import admin
# LearningGoal 모델만 import 합니다.
from .models import LearningGoal

# --- 삭제된 모델 등록 코드 ---
# UploadedPDF, TestSet, Question, UserTestAttempt, UserAnswer 등은
# 이제 flo_exam 앱에서 관리하므로 flo_my의 어드민에서는 제거합니다.
# -----------------------------

# 마이페이지의 핵심 기능인 '학습 목표' 모델만 어드민에 등록하여 관리합니다.
@admin.register(LearningGoal)
class LearningGoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'goal_type', 'due_date', 'achievement_rate', 'is_important', 'is_completed')
    list_filter = ('user', 'goal_type', 'is_important', 'is_completed', 'due_date')
    search_fields = ('title', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
