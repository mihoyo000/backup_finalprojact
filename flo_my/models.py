# flo_my/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

# --- PDF 테스트 기능 관련 모델 ---
class UploadedPDF(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="업로더")
    file = models.FileField(upload_to='pdfs/%Y/%m/%d/', verbose_name="PDF 파일")
    filename = models.CharField(max_length=255, verbose_name="원본 파일명")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="업로드 시간")
    
    def __str__(self): return f"{self.filename} (by {self.user.username})"
    class Meta:
        verbose_name = "업로드된 PDF"
        verbose_name_plural = "업로드된 PDF 목록"
        ordering = ['-uploaded_at']

class TestSet(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="생성자")
    source_pdf = models.ForeignKey(UploadedPDF, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="원본 PDF")
    title = models.CharField(max_length=255, default="생성된 시험", verbose_name="시험 제목")
    num_questions_requested = models.PositiveIntegerField(default=10, verbose_name="요청 문제 수")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성 시간")
    is_important = models.BooleanField(default=False, verbose_name="중요 표시")

    def __str__(self): return f"{self.title} (by {self.user.username})"
    class Meta:
        verbose_name = "시험 세트"
        verbose_name_plural = "시험 세트 목록"
        ordering = ['-created_at']

class Question(models.Model):
    test_set = models.ForeignKey(TestSet, on_delete=models.CASCADE, related_name='questions', verbose_name="시험 세트")
    content = models.TextField(verbose_name="문제 내용")
    explanation = models.TextField(null=True, blank=True, verbose_name="해설")
    order = models.PositiveIntegerField(default=0, verbose_name="문제 순서")

    def __str__(self): return f"Q{self.order or self.id}: {self.content[:50]}..."
    class Meta:
        verbose_name = "시험 문제"
        verbose_name_plural = "시험 문제 목록"
        ordering = ['test_set', 'order', 'id']

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices', verbose_name="관련 문제")
    content = models.CharField(max_length=500, verbose_name="보기 내용")
    is_correct = models.BooleanField(default=False, verbose_name="정답 여부")

    def __str__(self): return f"{self.content} (Correct: {self.is_correct})"
    class Meta:
        verbose_name = "객관식 보기"
        verbose_name_plural = "객관식 보기 목록"

class UserTestAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_attempts', verbose_name="응시자")
    test_set = models.ForeignKey(TestSet, on_delete=models.CASCADE, related_name='attempts', verbose_name="응시 시험")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="시작 시간")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="완료 시간")
    score = models.FloatField(null=True, blank=True, verbose_name="점수")
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
    selected_choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="선택한 보기")
    is_correct = models.BooleanField(null=True, blank=True, verbose_name="정답 여부")
    
    def __str__(self):
        answer_display = self.selected_choice.content if self.selected_choice else "답변 없음"
        return f"Answer to Q{self.question_id} by {self.attempt.user.username}: '{answer_display[:30]}...'"
    class Meta:
        verbose_name = "사용자 답변"
        verbose_name_plural = "사용자 답변 목록"
        unique_together = ('attempt', 'question')

# --- 마이페이지 학습목표 모델 ---
class LearningGoal(models.Model):
    GOAL_TYPE_CHOICES = [('TEST_RETAKE', 'Test 전체 다시 풀기'), ('INCORRECT_ANSWERS_RETAKE', '오답만 다시 풀기')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='learning_goals', verbose_name="사용자")
    title = models.CharField(max_length=255, verbose_name="학습 목표 제목")
    goal_type = models.CharField(max_length=30, choices=GOAL_TYPE_CHOICES, verbose_name="목표 유형")
    target_test_set = models.ForeignKey(TestSet, null=True, blank=True, on_delete=models.CASCADE, related_name='learning_goals_for_test_retake', verbose_name="대상 TestSet")
    target_attempt_for_incorrect_notes = models.ForeignKey(UserTestAttempt, null=True, blank=True, on_delete=models.CASCADE, related_name='learning_goals_for_incorrect_retake', verbose_name="오답노트 대상 응시기록")
    target_repetition_count = models.PositiveIntegerField(default=1, verbose_name="목표 반복 학습 횟수")
    current_repetition_count = models.PositiveIntegerField(default=0, verbose_name="현재 완료 횟수")
    due_date = models.DateField(verbose_name="학습 마감일")
    is_important = models.BooleanField(default=False, verbose_name="중요 목표 여부")
    is_completed = models.BooleanField(default=False, verbose_name="목표 달성 여부")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")
    
    def __str__(self): return f"{self.title} (사용자: {self.user.username})"
    @property
    def achievement_rate(self):
        if self.target_repetition_count > 0: return min(int((self.current_repetition_count / self.target_repetition_count) * 100), 100)
        return 0
    def save(self, *args, **kwargs):
        self.is_completed = self.target_repetition_count > 0 and self.current_repetition_count >= self.target_repetition_count
        super().save(*args, **kwargs)
    class Meta:
        verbose_name = "학습 목표"
        verbose_name_plural = "학습 목표 목록"
        ordering = ['-is_important', 'due_date', '-created_at']