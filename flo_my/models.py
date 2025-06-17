# flo_my/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

# --- flo_exam 앱의 모델을 정확하게 임포트합니다. ---
from flo_exam.models import ExamDocument, UserExamSession, UserAnswer


# ======================================================================
# 과거에 사용했던 자체 시험 모델들.
# 현재는 flo_exam 앱의 모델을 사용하므로, 더 이상 필요하지 않습니다.
# 데이터 손실을 방지하기 위해 삭제 대신 주석 처리합니다.
# 만약 이 모델들을 참조하는 다른 코드가 있다면(예: forms.py, admin.py),
# 해당 코드도 함께 수정하거나 주석 처리해야 합니다.
# ======================================================================

# class UploadedPDF(models.Model):
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="업로더")
#     file = models.FileField(upload_to='pdfs/%Y/%m/%d/', verbose_name="PDF 파일")
#     filename = models.CharField(max_length=255, verbose_name="원본 파일명")
#     uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="업로드 시간")
#     def __str__(self): return f"{self.filename} (by {self.user.username})"
#     class Meta:
#         verbose_name = "업로드된 PDF"
#         verbose_name_plural = "업로드된 PDF 목록"
#         ordering = ['-uploaded_at']

# class TestSet(models.Model):
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="생성자")
#     source_pdf = models.ForeignKey(UploadedPDF, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="원본 PDF")
#     title = models.CharField(max_length=255, default="생성된 시험", verbose_name="시험 제목")
#     num_questions_requested = models.PositiveIntegerField(default=10, verbose_name="요청 문제 수")
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성 시간")
#     is_important = models.BooleanField(default=False, verbose_name="중요 표시")
#     def __str__(self): return f"{self.title} (by {self.user.username})"
#     class Meta:
#         verbose_name = "시험 세트"
#         verbose_name_plural = "시험 세트 목록"
#         ordering = ['-created_at']

# class Question(models.Model):
#     ...

# class Choice(models.Model):
#     ...

# class UserTestAttempt(models.Model):
#     ...

# class UserAnswer(models.Model):
#     # 이 모델은 flo_exam의 UserAnswer와 이름이 같아 혼동을 유발할 수 있습니다.
#     ...


# ======================================================================
# 현재 실제로 사용하는 유일한 모델: LearningGoal
# ======================================================================

class LearningGoal(models.Model):
    """
    사용자의 학습 목표를 관리하는 모델.
    flo_exam 앱의 ExamDocument와 UserExamSession을 직접 참조합니다.
    """
    GOAL_TYPE_CHOICES = [
        ('TEST_RETAKE', '시험 다시 풀기'),
        ('INCORRECT_ANSWERS_RETAKE', '오답만 다시 풀기')
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='learning_goals', verbose_name="사용자")
    title = models.CharField(max_length=255, verbose_name="학습 목표 제목")
    goal_type = models.CharField(max_length=30, choices=GOAL_TYPE_CHOICES, verbose_name="목표 유형")
    
    target_test_set = models.ForeignKey(
        ExamDocument,
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='learning_goals_for_test_retake', 
        verbose_name="대상 시험 (전체 다시 풀기)"
    )
    target_attempt_for_incorrect_notes = models.ForeignKey(
        UserExamSession,
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='learning_goals_for_incorrect_retake', 
        verbose_name="오답노트 대상 응시기록"
    )
    
    target_repetition_count = models.PositiveIntegerField(default=1, verbose_name="목표 반복 학습 횟수")
    current_repetition_count = models.PositiveIntegerField(default=0, verbose_name="현재 완료 횟수")
    due_date = models.DateField(verbose_name="학습 마감일")
    is_important = models.BooleanField(default=False, verbose_name="중요 목표 여부")
    is_completed = models.BooleanField(default=False, verbose_name="목표 달성 여부")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    def __str__(self):
        return f"{self.title} (사용자: {self.user.username})"

    @property
    def achievement_rate(self):
        if self.target_repetition_count > 0:
            return min(int((self.current_repetition_count / self.target_repetition_count) * 100), 100)
        return 0

    def save(self, *args, **kwargs):
        self.is_completed = self.target_repetition_count > 0 and self.current_repetition_count >= self.target_repetition_count
        super().save(*args, **kwargs)
        
    class Meta:
        verbose_name = "학습 목표"
        verbose_name_plural = "학습 목표 목록"
        ordering = ['-is_important', 'due_date', '-created_at']
