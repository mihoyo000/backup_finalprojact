# flo_exam/models.py
from django.db import models
from django.contrib.auth.models import User # 로그인 기능은 나중에 추가 예정

class ExamDocument(models.Model):
    # author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="작성자")
    title = models.CharField(max_length=255, verbose_name="제목")
    pdf_file = models.FileField(upload_to='uploaded_pdfs/', verbose_name="PDF 파일")
    
    NUM_QUESTIONS_CHOICES = [
        (10, '10문제'),
        (20, '20문제'),
        (25, '25문제'),
    ]
    num_questions_requested = models.IntegerField(
        choices=NUM_QUESTIONS_CHOICES,
        default=10,
        verbose_name="문항수"
    )

    QUESTION_TYPE_CHOICES = [
        ('객관식', '객관식(4지선다)'),
        ('단답형', '단답형'),
    ]
    question_type_requested = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default='객관식',
        verbose_name="문제 유형"
    )
    
    subject_area = models.CharField(max_length=100, verbose_name="분야", help_text="예: 수학, 정보처리기사 등")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="업로드 일시")

    STATUS_CHOICES = [
        ('PENDING', '대기 중'),
        ('PROCESSING', '문제 생성 중'),
        ('COMPLETED', '생성 완료'),
        ('FAILED', '생성 실패'),
    ]
    processing_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return self.title


class GeneratedExam(models.Model):
    """AI가 생성한 전체 시험 세트"""
    exam_document = models.OneToOneField(ExamDocument, on_delete=models.CASCADE, related_name="generated_exam")
    # user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Generated Exam for: {self.exam_document.title}"

class GeneratedQuestion(models.Model):
    """AI가 생성한 개별 문제"""
    exam = models.ForeignKey(GeneratedExam, on_delete=models.CASCADE, related_name="questions")
    question_number = models.IntegerField(verbose_name="문제 번호")
    question_text = models.TextField(verbose_name="문제 내용")
    question_type = models.CharField(max_length=20, verbose_name="문제 유형") # 'multiple_choice' or 'short_answer'
    
    option1 = models.CharField(max_length=500, blank=True, null=True, verbose_name="선택지1")
    option2 = models.CharField(max_length=500, blank=True, null=True, verbose_name="선택지2")
    option3 = models.CharField(max_length=500, blank=True, null=True, verbose_name="선택지3")
    option4 = models.CharField(max_length=500, blank=True, null=True, verbose_name="선택지4")
    
    correct_answer = models.TextField(verbose_name="정답")
    explanation = models.TextField(verbose_name="해설", blank=True, null=True)

    def __str__(self):
        return f"Q{self.question_number} ({self.exam.exam_document.title})"

    @property
    def options_list(self):
        """템플릿에서 객관식 선택지를 리스트로 쉽게 사용하기 위한 헬퍼"""
        opts = []
        if self.question_type == "multiple_choice": # 또는 API에서 받은 타입명
            if self.option1: opts.append(self.option1)
            if self.option2: opts.append(self.option2)
            if self.option3: opts.append(self.option3)
            if self.option4: opts.append(self.option4)
        return opts