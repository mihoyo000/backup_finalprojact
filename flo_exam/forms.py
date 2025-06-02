# flo_exam/forms.py
from django import forms
from .models import ExamDocument

class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = ExamDocument
        fields = ['pdf_file', 'num_questions', 'question_type', 'subject_area', 'title'] # 순서 조정
        widgets = {
            'num_questions': forms.RadioSelect,
            'question_type': forms.RadioSelect,
            'subject_area': forms.TextInput(attrs={
                'placeholder': '선택 또는 직접 입력 (예: 정보처리기사)' # 원본이미지 참고하여 수정
            }),
            'title': forms.TextInput(attrs={
                'placeholder': '문제집 제목을 입력해주세요' # 원본이미지 참고하여 수정
            }),
            # pdf_file 위젯은 기본 FileInput 사용
        }
        labels = {
            'pdf_file': 'PDF 파일 선택', # 원본에는 레이블이 없지만, 명확성을 위해 추가
            'num_questions': '문항수',
            'question_type': '문제 유형',
            'subject_area': '분야',
            'title': '제목', # 원본에는 레이블이 없지만, 명확성을 위해 추가
        }
        # help_texts 등을 추가하여 사용자에게 더 많은 정보 제공 가능