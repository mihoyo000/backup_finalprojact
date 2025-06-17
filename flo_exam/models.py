from django.db import models
from django.conf import settings
from django.utils import timezone # 시간 관련 기능

# 1. 사용자가 업로드한 PDF 문서 및 요청 정보를 담는 모델
# ==============================================================================
class ExamDocument(models.Model):
    # 로그인 기능 구현 시 작성자를 연결합니다.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, # 작성자 계정 삭제 시 이 필드를 NULL로 설정 (문서는 남김)
        null=True, 
        blank=True, # 관리자 페이지 등에서 빈 값 허용
        verbose_name="작성자"
    )
    title = models.CharField(max_length=255, verbose_name="문서 제목")
    pdf_file = models.FileField(upload_to='uploaded_pdfs/', verbose_name="PDF 파일")
    
    # 사용자가 요청한 문항 수 선택지 (폼에서도 사용 가능)
    NUM_QUESTIONS_CHOICES = [
        (10, '10문제'),
        (20, '20문제'),
        (25, '25문제'),
    ]
    num_questions_requested = models.IntegerField(
        verbose_name="요청 문항수", 
        choices=NUM_QUESTIONS_CHOICES, 
        default=10
    )
    
    # 사용자가 요청한 문제 유형 선택지 (폼에서도 사용 가능)
    QUESTION_TYPE_CHOICES = [
        ('객관식', '객관식(4지선다)'),
        ('단답형', '단답형'),
    ]
    question_type_requested = models.CharField(
        max_length=20, 
        verbose_name="요청 문제 유형", 
        choices=QUESTION_TYPE_CHOICES, 
        default='객관식'
    )
    subject_area = models.CharField(
        max_length=100, 
        verbose_name="분야", 
        help_text="예: 수학, 정보처리기사, HTML, CSS 등"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="업로드 일시")
    
    # AI 처리 상태 (선택 사항, 로딩 페이지나 재시도 로직에 활용 가능)
    PROCESSING_STATUS_CHOICES = [
        ('PENDING', '대기 중'),
        ('PROCESSING', '문제 생성 중'),
        ('COMPLETED', '생성 완료'),
        ('FAILED', '생성 실패'),
    ]
    processing_status = models.CharField(
        max_length=20, 
        choices=PROCESSING_STATUS_CHOICES, 
        default='PENDING',
        verbose_name="처리 상태"
    )

     # ★★★★★★★★★ 마이페이지 중요도 설정을 위해 추가 25/06/16★★★★★★★★★
    is_important = models.BooleanField(default=False, verbose_name="중요 표시")

    def __str__(self):
        return self.title if self.title else f"ExamDocument {self.id}"

    class Meta:
        verbose_name = "업로드된 PDF 문서"
        verbose_name_plural = "업로드된 PDF 문서들"
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title if self.title else f"ExamDocument {self.id}"

    class Meta:
        verbose_name = "업로드된 PDF 문서"
        verbose_name_plural = "업로드된 PDF 문서들"
        ordering = ['-uploaded_at']


# 2. AI가 생성한 전체 시험 세트를 나타내는 모델
# ==============================================================================
class GeneratedExam(models.Model):
    # 어떤 ExamDocument를 기반으로 생성되었는지 연결 (1:1 관계)
    exam_document = models.OneToOneField(
        ExamDocument, 
        on_delete=models.CASCADE, # 원본 ExamDocument 삭제 시 함께 삭제
        related_name="generated_exam", # ExamDocument 객체에서 .generated_exam으로 접근 가능
        verbose_name="원본 PDF 문서"
    )
    # user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="생성 요청자")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성 일시")
    
    def __str__(self):
        return f"생성된 시험 (원본: {self.exam_document.title})"

    class Meta:
        verbose_name = "생성된 시험 세트"
        verbose_name_plural = "생성된 시험 세트들"
        ordering = ['-created_at']


# 3. AI가 생성한 개별 문제를 담는 모델
# ==============================================================================
class GeneratedQuestion(models.Model):
    # 어떤 GeneratedExam에 속한 문제인지 연결 (N:1 관계)
    exam = models.ForeignKey(
        GeneratedExam, 
        on_delete=models.CASCADE, 
        related_name="questions", # GeneratedExam 객체에서 .questions.all() 등으로 접근 가능
        verbose_name="소속 시험"
    )
    question_number = models.IntegerField(verbose_name="문제 번호")
    question_text = models.TextField(verbose_name="문제 내용")
    
    # AI가 응답한 문제 유형 (예: "multiple_choice", "short_answer")
    question_type = models.CharField(max_length=20, verbose_name="실제 문제 유형")
    
    # 객관식 선택지 (4개까지 가정)
    option1 = models.CharField(max_length=500, blank=True, null=True, verbose_name="선택지 1")
    option2 = models.CharField(max_length=500, blank=True, null=True, verbose_name="선택지 2")
    option3 = models.CharField(max_length=500, blank=True, null=True, verbose_name="선택지 3")
    option4 = models.CharField(max_length=500, blank=True, null=True, verbose_name="선택지 4")
    
    correct_answer = models.TextField(verbose_name="정답") # 객관식은 선택지 텍스트, 단답형은 답안 텍스트
    explanation = models.TextField(verbose_name="해설", blank=True, null=True)

    def __str__(self):
        return f"문제 {self.question_number} ({self.exam.exam_document.title})"

    @property
    def options_list(self):
        """템플릿이나 다른 코드에서 객관식 선택지를 리스트로 쉽게 사용하기 위한 헬퍼."""
        opts = []
        if self.question_type == "multiple_choice": # API 응답과 일치하는 문자열 사용
            if self.option1: opts.append(self.option1)
            if self.option2: opts.append(self.option2)
            if self.option3: opts.append(self.option3)
            if self.option4: opts.append(self.option4)
        return opts
    
    def to_dict(self):
        """JavaScript로 문제 데이터를 전달하기 위한 딕셔너리 변환 메소드."""
        # 문제 풀이 시에는 정답과 해설을 클라이언트에 바로 보내지 않는 것이 일반적.
        # 여기서는 초기 문제 UI 구성을 위한 최소 정보만 포함하거나,
        # 또는 모든 정보를 보내되 JS에서 선택적으로 사용하도록 할 수 있음.
        # 현재 views.py는 이 메소드의 결과를 그대로 JS로 보내므로, options를 포함해야 함.
        return {
            'id': self.id,
            'question_number': self.question_number,
            'question_text': self.question_text,
            'question_type': self.question_type,
            'options': self.options_list, 
            # 'correct_answer': self.correct_answer, # JS에서 문제 풀이 UI 생성 시에는 사용하지 않음
            # 'explanation': self.explanation,      # JS에서 문제 풀이 UI 생성 시에는 사용하지 않음
        }

    class Meta:
        verbose_name = "생성된 문제"
        verbose_name_plural = "생성된 문제들"
        ordering = ['exam', 'question_number']


# 4. 사용자의 특정 시험 응시 세션을 기록하는 모델
# ==============================================================================
class UserExamSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, # 사용자 삭제 시 관련 세션도 삭제
        null=True, blank=True, # 비로그인 사용자도 응시 가능하도록
        verbose_name="응시자"
    )
    generated_exam = models.ForeignKey(
        GeneratedExam, 
        on_delete=models.CASCADE, # 원본 시험 삭제 시 세션도 삭제
        verbose_name="응시한 시험"
    )
    start_time = models.DateTimeField(auto_now_add=True, verbose_name="시작 시간")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="종료 시간") # 채점 완료 시 기록
    score = models.FloatField(null=True, blank=True, verbose_name="점수") # 0.0 ~ 100.0
    # --- ▼▼▼ 마이페이지 오답노트 ▼▼▼ ---
    is_important = models.BooleanField(default=False) 
    # --- ▲▲▲ 25.06.16 ▲▲▲ ---

    def __str__(self):
        user_str = self.user.username if self.user else "익명 사용자"
        return f"{self.generated_exam.exam_document.title} 응시 세션 (응시자: {user_str})"

    class Meta:
        verbose_name = "사용자 시험 응시 세션"
        verbose_name_plural = "사용자 시험 응시 세션들"
        ordering = ['-start_time']


# 5. 사용자가 각 문제에 대해 제출한 답을 기록하는 모델
# ==============================================================================
class UserAnswer(models.Model):
    session = models.ForeignKey(
        UserExamSession, 
        on_delete=models.CASCADE, 
        related_name="answers", # UserExamSession 객체에서 .answers.all() 등으로 접근
        verbose_name="응시 세션"
    )
    question = models.ForeignKey(
        GeneratedQuestion, 
        on_delete=models.CASCADE, # 문제가 삭제되면 해당 답안도 의미 없으므로 삭제
        verbose_name="해당 문제"
    )
    submitted_answer = models.TextField(verbose_name="제출한 답", blank=True, null=True) # 사용자가 답을 안 낼 수도 있음
    is_correct = models.BooleanField(null=True, verbose_name="정답 여부") # 채점 전에는 Null, 채점 후 True/False

    def __str__(self):
        q_num = self.question.question_number
        user_str = self.session.user.username if self.session.user else "익명"
        return f"{user_str}의 문제 {q_num} 답: {self.submitted_answer[:20]}"

    def to_dict_with_question(self):
        """결과 화면 등에서 JavaScript로 상세 정보를 전달하기 위한 딕셔너리 변환."""
        return {
            'question_id': self.question.id,
            'question_number': self.question.question_number,
            'question_text': self.question.question_text,
            'options': self.question.options_list, # 문제의 선택지 정보도 포함
            'submitted_answer': self.submitted_answer,
            'correct_answer': self.question.correct_answer,
            'explanation': self.question.explanation,
            'is_correct': self.is_correct
        }

    class Meta:
        verbose_name = "사용자 제출 답안"
        verbose_name_plural = "사용자 제출 답안들"
        ordering = ['session', 'question__question_number'] # 세션 및 문제 번호 순으로 정렬