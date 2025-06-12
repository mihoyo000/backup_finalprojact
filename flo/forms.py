# flo/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm # 회원가입 폼을 위해 추가
from django.contrib.auth.models import User # Django 기본 User 모델 (또는 커스텀 User 모델 경로)
from .models import Post, Attachment, Comment, Category
from tinymce.widgets import TinyMCE # TinyMCE 위젯
from .models import UploadedPDF
from .models import LearningGoal, TestSet, UserTestAttempt
from django.utils import timezone
from datetime import timedelta

# ... (AttachmentForm, PostForm, CommentForm, CustomUserCreationForm, PDFUploadForm, LearningGoalForm은 그대로 유지) ...
class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ['file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control-file attachment-true-input'}),
        }
        labels = {
            'file': '',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'pk') and self.instance.pk:
            self.fields['file'].required = False

class PostForm(forms.ModelForm):
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all().order_by('name'),
        widget=forms.SelectMultiple(attrs={'class': 'categories-select2-target'}),
        required=False,
        label="카테고리 선택 (최대 5개)",
        help_text="게시글과 관련된 카테고리를 최대 5개까지 선택해주세요."
    )
    class Meta:
        model = Post
        fields = ['categories', 'title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control','placeholder': '제목을 입력해 주세요.'}),
            'content': TinyMCE(attrs={'rows': 15,}),
        }
        labels = {'title': '','content': '',}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['categories'].initial = self.instance.categories.all()
    def clean_categories(self):
        selected_categories = self.cleaned_data.get('categories')
        if selected_categories and len(selected_categories) > 5:
            raise forms.ValidationError("카테고리는 최대 5개까지만 선택할 수 있습니다.")
        return selected_categories

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '댓글을 입력하세요...'}),}
        labels = {'content': '',}

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control mb-2', 'placeholder': field.label})
            if field_name == 'username': field.widget.attrs['placeholder'] = '사용자 이름'

class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = UploadedPDF
        fields = ['file']
        widgets = {'file': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),}
        labels = {'file': 'PDF 파일 선택',}
    def clean_file(self):
        file = self.cleaned_data.get('file', False)
        if file:
            if not file.name.endswith(('.pdf', '.PDF')):
                raise forms.ValidationError("PDF 파일만 업로드 가능합니다. (.pdf 또는 .PDF)")
        elif not self.instance.pk:
             raise forms.ValidationError("PDF 파일을 선택해주세요.")
        return file

# --- 학습 목표 폼 ---
class LearningGoalForm(forms.ModelForm):
    title = forms.CharField(
        max_length=255,
        required=False,
        label="학습 목표 제목",
        help_text="비워두시면 Test 제목 등을 기반으로 자동 생성됩니다. 직접 수정도 가능합니다.",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '예: 미적분 1단원 마스터하기'})
    )

    goal_type = forms.ChoiceField(
        choices=LearningGoal.GOAL_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="목표 유형"
    )
    
    target_test_set = forms.ModelChoiceField(
        queryset=TestSet.objects.none(),
        required=False,
        label="대상 Test (전체 다시 풀기)",
        empty_label="--------- (Test 전체 다시 풀기 선택 시 필수)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    target_attempt_for_incorrect_notes = forms.ModelChoiceField(
        queryset=UserTestAttempt.objects.none(),
        required=False,
        label="대상 시험 응시 기록 (오답만 다시 풀기)",
        empty_label="--------- (오답만 다시 풀기 선택 시 필수)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    target_repetition_count = forms.IntegerField(
        min_value=1,
        initial=1,
        label="목표 반복 횟수",
        help_text="이 목표를 몇 번 반복해서 학습할지 설정합니다.",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'})
    )
    
    due_date = forms.DateField(
        label="학습 마감일 (일주일 이내)",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="오늘부터 일주일 이내의 날짜를 선택해주세요."
    )

    is_important = forms.BooleanField(
        required=False,
        label="중요 목표로 표시",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = LearningGoal
        fields = ['title', 'goal_type', 'target_test_set', 'target_attempt_for_incorrect_notes', 
                  'target_repetition_count', 'due_date', 'is_important']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['target_test_set'].queryset = TestSet.objects.filter(user=user).order_by('-created_at')
            # 'completed_at'을 'started_at'으로 수정하여 미완료 시험도 포함할 수 있도록 함
            self.fields['target_attempt_for_incorrect_notes'].queryset = UserTestAttempt.objects.filter(
                user=user
            ).select_related('test_set').order_by('-started_at')
        
        today = timezone.now().date()
        self.fields['due_date'].widget.attrs['min'] = today.isoformat()
        self.fields['due_date'].widget.attrs['max'] = (today + timedelta(days=6)).isoformat()

        if self.instance and self.instance.pk:
            self.fields['goal_type'].disabled = True
            self.fields['goal_type'].help_text = "목표 유형은 생성 후 변경할 수 없습니다."
            if self.instance.goal_type == 'TEST_RETAKE':
                self.fields['target_test_set'].disabled = True
                self.fields['target_test_set'].help_text = "대상 Test는 변경할 수 없습니다."
                self.fields['target_attempt_for_incorrect_notes'].widget = forms.HiddenInput()
            elif self.instance.goal_type == 'INCORRECT_ANSWERS_RETAKE':
                self.fields['target_attempt_for_incorrect_notes'].disabled = True
                self.fields['target_attempt_for_incorrect_notes'].help_text = "대상 응시기록은 변경할 수 없습니다."
                self.fields['target_test_set'].widget = forms.HiddenInput()
            else:
                self.fields['target_test_set'].disabled = True
                self.fields['target_attempt_for_incorrect_notes'].disabled = True


    def clean(self):
        cleaned_data = super().clean()
        is_edit_mode = self.instance and self.instance.pk
        goal_type = self.instance.goal_type if is_edit_mode and self.fields['goal_type'].disabled else cleaned_data.get('goal_type')
        target_test_set = cleaned_data.get('target_test_set')
        target_attempt = cleaned_data.get('target_attempt_for_incorrect_notes')

        if not is_edit_mode:
            if goal_type == 'TEST_RETAKE':
                if not target_test_set:
                    self.add_error('target_test_set', 'Test 전체 다시 풀기를 선택한 경우, 대상 Test를 지정해야 합니다.')
                cleaned_data['target_attempt_for_incorrect_notes'] = None 
            elif goal_type == 'INCORRECT_ANSWERS_RETAKE':
                if not target_attempt:
                    self.add_error('target_attempt_for_incorrect_notes', '오답만 다시 풀기를 선택한 경우, 대상 시험 응시 기록을 지정해야 합니다.')
                cleaned_data['target_test_set'] = None
            elif not goal_type:
                self.add_error('goal_type', '목표 유형을 선택해주세요.')
        
        due_date = cleaned_data.get('due_date')
        if due_date:
            today = timezone.now().date()
            if not (today <= due_date <= today + timedelta(days=6)):
                self.add_error('due_date', '마감일은 오늘부터 일주일 이내로 설정해야 합니다.')
        return cleaned_data

class TestSetSearchForm(forms.Form):
    search_title = forms.CharField(
        required=False,
        label="", # 라벨을 템플릿에서 직접 제어하므로 비워둠
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '제목으로 검색'})
    )
    search_date_start = forms.DateField(
        required=False,
        label="",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'})
    )
    search_date_end = forms.DateField(
        required=False,
        label="",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'})
    )
    show_important_only = forms.BooleanField(
        required=False,
        label="",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean(self):
        cleaned_data = super().clean()
        date_start = cleaned_data.get('search_date_start')
        date_end = cleaned_data.get('search_date_end')

        if date_start and date_end and date_start > date_end:
            self.add_error('search_date_end', '종료일은 시작일보다 빠를 수 없습니다.')
        
        return cleaned_data

# ▼▼▼ 새로 추가된 폼 ▼▼▼
class IncorrectNoteSearchForm(forms.Form):
    """오답노트 목록 검색/필터링을 위한 폼"""
    search_title = forms.CharField(
        required=False, 
        label="", # 라벨은 템플릿에서 직접 제어
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '시험지명으로 검색'})
    )
    search_date_start = forms.DateField(
        required=False, 
        label="",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'})
    )
    search_date_end = forms.DateField(
        required=False, 
        label="",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'})
    )
    show_important_only = forms.BooleanField(
        required=False, 
        label="",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean(self):
        cleaned_data = super().clean()
        date_start = cleaned_data.get('search_date_start')
        date_end = cleaned_data.get('search_date_end')

        if date_start and date_end and date_start > date_end:
            self.add_error('search_date_end', '종료일은 시작일보다 빠를 수 없습니다.')
        
        return cleaned_data
