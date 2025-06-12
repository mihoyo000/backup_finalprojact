# flo_my/forms.py
from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import (
    UploadedPDF, LearningGoal, TestSet, UserTestAttempt
)

class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = UploadedPDF
        fields = ['file']
        widgets = {'file': forms.ClearableFileInput(attrs={'class': 'form-control-file'})}
        labels = {'file': 'PDF 파일 선택'}
    def clean_file(self):
        file = self.cleaned_data.get('file', False)
        if file:
            if not file.name.endswith(('.pdf', '.PDF')):
                raise forms.ValidationError("PDF 파일만 업로드 가능합니다. (.pdf 또는 .PDF)")
        elif not self.instance.pk:
             raise forms.ValidationError("PDF 파일을 선택해주세요.")
        return file

class LearningGoalForm(forms.ModelForm):
    title = forms.CharField(max_length=255, required=False, label="학습 목표 제목", help_text="비워두시면 Test 제목 등을 기반으로 자동 생성됩니다. 직접 수정도 가능합니다.", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 미적분 1단원 마스터하기'}))
    goal_type = forms.ChoiceField(choices=LearningGoal.GOAL_TYPE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}), label="목표 유형")
    target_test_set = forms.ModelChoiceField(queryset=TestSet.objects.none(), required=False, label="대상 Test (전체 다시 풀기)", empty_label="--------- (Test 전체 다시 풀기 선택 시 필수)", widget=forms.Select(attrs={'class': 'form-select'}))
    target_attempt_for_incorrect_notes = forms.ModelChoiceField(queryset=UserTestAttempt.objects.none(), required=False, label="대상 시험 응시 기록 (오답만 다시 풀기)", empty_label="--------- (오답만 다시 풀기 선택 시 필수)", widget=forms.Select(attrs={'class': 'form-select'}))
    target_repetition_count = forms.IntegerField(min_value=1, initial=1, label="목표 반복 횟수", help_text="이 목표를 몇 번 반복해서 학습할지 설정합니다.", widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}))
    due_date = forms.DateField(label="학습 마감일 (일주일 이내)", widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), help_text="오늘부터 일주일 이내의 날짜를 선택해주세요.")
    is_important = forms.BooleanField(required=False, label="중요 목표로 표시", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    
    class Meta:
        model = LearningGoal
        fields = ['title', 'goal_type', 'target_test_set', 'target_attempt_for_incorrect_notes', 'target_repetition_count', 'due_date', 'is_important']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['target_test_set'].queryset = TestSet.objects.filter(user=user).order_by('-created_at')
            self.fields['target_attempt_for_incorrect_notes'].queryset = UserTestAttempt.objects.filter(user=user).select_related('test_set').order_by('-started_at')
        today = timezone.now().date()
        self.fields['due_date'].widget.attrs['min'] = today.isoformat()
        self.fields['due_date'].widget.attrs['max'] = (today + timedelta(days=6)).isoformat()
        if self.instance and self.instance.pk:
            self.fields['goal_type'].disabled = True
            # ... (이하 __init__ 메서드의 나머지 코드는 그대로 유지) ...

    def clean(self):
        # ... (clean 메서드 코드는 그대로 유지) ...
        return super().clean()

class TestSetSearchForm(forms.Form):
    search_title = forms.CharField(required=False, label="", widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '제목으로 검색'}))
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

class IncorrectNoteSearchForm(forms.Form):
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
