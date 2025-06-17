# flo_my/forms.py

from django import forms
from django.utils import timezone
from datetime import timedelta

# --- 1. 우리 앱의 모델 ---
# 현재 사용하는 LearningGoal 모델만 남깁니다.
from .models import LearningGoal

# --- 2. 다른 앱의 모델 ---
from flo_exam.models import ExamDocument, UserExamSession


# ======================================================================
# 더 이상 사용하지 않는 과거의 폼들은 모두 주석 처리 또는 삭제합니다.
# ======================================================================

# class PDFUploadForm(forms.ModelForm):
#     ...

# class TestSetSearchForm(forms.Form):
#     ...


# ======================================================================
# 현재 실제로 사용하는 폼들
# ======================================================================

class LearningGoalForm(forms.ModelForm):
    """
    새로운 학습 목표 생성을 위한 폼입니다.
    """
    # 필드 정의는 이전과 동일하게 유지합니다.
    title = forms.CharField(max_length=255, required=False, label="학습 목표 제목", help_text="비워두시면 시험지 제목 등을 기반으로 자동 생성됩니다.", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 미적분 1단원 마스터하기'}))
    goal_type = forms.ChoiceField(choices=LearningGoal.GOAL_TYPE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}), label="목표 유형")
    target_test_set = forms.ModelChoiceField(queryset=ExamDocument.objects.none(), required=False, label="대상 시험지 (전체 다시 풀기)", empty_label="--------- (시험 다시 풀기 선택 시 필수)", widget=forms.Select(attrs={'class': 'form-select'}))
    target_attempt_for_incorrect_notes = forms.ModelChoiceField(queryset=UserExamSession.objects.none(), required=False, label="대상 응시 기록 (오답만 다시 풀기)", empty_label="--------- (오답만 다시 풀기 선택 시 필수)", widget=forms.Select(attrs={'class': 'form-select'}))
    target_repetition_count = forms.IntegerField(min_value=1, initial=1, label="목표 반복 횟수", help_text="이 목표를 몇 번 반복해서 학습할지 설정합니다.", widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}))
    due_date = forms.DateField(label="학습 마감일", widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), help_text="오늘부터 7일 이내의 날짜를 선택해주세요.")
    is_important = forms.BooleanField(required=False, label="중요 목표로 표시", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    
    class Meta:
        model = LearningGoal
        fields = ['title', 'goal_type', 'target_test_set', 'target_attempt_for_incorrect_notes', 'target_repetition_count', 'due_date', 'is_important']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['target_test_set'].queryset = ExamDocument.objects.filter(author=user).order_by('-uploaded_at')
            user_sessions = UserExamSession.objects.filter(user=user).select_related('generated_exam__exam_document').order_by('-start_time')
            self.fields['target_attempt_for_incorrect_notes'].queryset = user_sessions
            self.fields['target_attempt_for_incorrect_notes'].label_from_instance = lambda obj: f"{obj.generated_exam.exam_document.title} (응시일: {obj.start_time.strftime('%y-%m-%d')})"

        today = timezone.now().date()
        self.fields['due_date'].widget.attrs['min'] = today.isoformat()
        self.fields['due_date'].widget.attrs['max'] = (today + timedelta(days=6)).isoformat()
        
        if self.instance and self.instance.pk:
            self.fields['goal_type'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        goal_type = cleaned_data.get('goal_type')
        if goal_type == 'TEST_RETAKE' and not cleaned_data.get('target_test_set'):
            self.add_error('target_test_set', '시험 다시 풀기 목표는 대상 시험지를 반드시 선택해야 합니다.')
        if goal_type == 'INCORRECT_ANSWERS_RETAKE' and not cleaned_data.get('target_attempt_for_incorrect_notes'):
            self.add_error('target_attempt_for_incorrect_notes', '오답 다시 풀기 목표는 대상 응시 기록을 반드시 선택해야 합니다.')
        return cleaned_data


class LearningGoalEditForm(forms.ModelForm):
    """
    학습 목표 수정을 위한 폼입니다. 수정 가능한 필드만 포함합니다.
    """
    class Meta:
        model = LearningGoal
        # 수정 가능한 필드만 명시합니다.
        fields = ['title', 'target_repetition_count', 'due_date', 'is_important']
        # 각 필드에 맞는 위젯을 설정합니다.
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'target_repetition_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'is_important': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class IncorrectNoteSearchForm(forms.Form):
    """
    오답 노트 검색을 위한 폼입니다. (현재 사용되고 있다면 유지)
    """
    search_title = forms.CharField(required=False, label="", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '시험지명으로 검색'}))
    search_date_start = forms.DateField(required=False, label="", widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    search_date_end = forms.DateField(required=False, label="", widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    show_important_only = forms.BooleanField(required=False, label="", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def clean(self):
        cleaned_data = super().clean()
        date_start = cleaned_data.get('search_date_start')
        date_end = cleaned_data.get('search_date_end')
        if date_start and date_end and date_start > date_end:
            self.add_error('search_date_end', '종료일은 시작일보다 빠를 수 없습니다.')
        return cleaned_data