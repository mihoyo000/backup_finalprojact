# flo_exam/models.py
from django.db import models

class ExamDocument(models.Model):
    title = models.CharField(max_length=255, verbose_name="제목")
    pdf_file = models.FileField(upload_to='uploaded_pdfs/', verbose_name="PDF 파일")
    
    NUM_QUESTIONS_CHOICES = [
        (10, '10문제'),
        (20, '20문제'),
        (25, '25문제'),
    ]
    num_questions = models.IntegerField(
        choices=NUM_QUESTIONS_CHOICES,
        default=10,
        verbose_name="문항수"
    )

    QUESTION_TYPE_CHOICES = [
        ('객관식', '객관식(4지선다)'),
        ('단답형', '단답형'),
    ]
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default='객관식',
        verbose_name="문제 유형"
    )
    
    subject_area = models.CharField(max_length=100, verbose_name="분야", help_text="예: 수학, 정보처리기사 등")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="업로드 일시")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "업로드된 시험 문서"
        verbose_name_plural = "업로드된 시험 문서들"