from django import forms
from .models import ExamDocument # 모델 임포트
from .fields import SubjectAreaField # 이전 답변의 SubjectAreaField

class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = ExamDocument
        fields = ['pdf_file', 'num_questions_requested', 'question_type_requested', 'subject_area', 'title']
        widgets = {
            # 모델 필드에 choices가 정의되어 있으면 RadioSelect가 자동으로 해당 choices를 사용합니다.
            'num_questions_requested': forms.RadioSelect(), 
            'question_type_requested': forms.RadioSelect(),
            'title': forms.TextInput(attrs={'placeholder': '문제집 제목을 입력해주세요'}),
        }
        labels = {
            'pdf_file': 'PDF 파일 선택:',
            'num_questions_requested': '문항수:',
            'question_type_requested': '문제 유형:',
            #'subject_area': '분야:',
            'title': '제목:',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None) # 로그인은 나중에
        super().__init__(*args, **kwargs)

        # --- subject_area 필드 동적 choices 설정 (이전과 동일) ---
        base_choices_list = [
            ('수학', '수학'), ('정보처리기사', '정보처리기사'), ('영어', '영어'), ('코딩 테스트', '코딩 테스트'),
        ]
        default_empty_choice = [('', '--------')]
        
        existing_db_subjects = list(
            ExamDocument.objects.exclude(subject_area__exact='')
                               .values_list('subject_area', flat=True)
                               .distinct()
                               .order_by('subject_area')
        )

        final_choices_dict = {val: lbl for val, lbl in base_choices_list if val}
        for subject_value in existing_db_subjects:
            if subject_value and subject_value not in final_choices_dict:
                final_choices_dict[subject_value] = subject_value
        
        sorted_final_choices = sorted(final_choices_dict.items())
        dynamic_choices = default_empty_choice + sorted_final_choices

        self.fields['subject_area'] = SubjectAreaField(
            choices=dynamic_choices, 
            required=False, # 분야는 필수가 아닐 수 있음
            label="분야:", # 레이블 뒤에 ':' 추가 (일관성)
            help_text="드롭다운에서 선택하거나 직접 입력하세요."
        )
        # ---------------------------------------------------------

        # 폼 필드의 레이블 뒤에 ':'가 자동으로 붙지 않는 경우가 있으므로, 일관성을 위해 수동 추가
        for field_name, field in self.fields.items():
            if not field.label.endswith(':'):
                 field.label = field.label + ":"

        if self.instance and self.instance.pk and self.instance.subject_area:
            self.initial['subject_area'] = self.instance.subject_area