#flo/forms.py
from django import forms
from .models import Post, Attachment, Comment, Category
from tinymce.widgets import TinyMCE # TinyMCE 위젯

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
        instance_pk = None
        instance_type = None
        if self.instance:
            instance_pk = getattr(self.instance, 'pk', 'No PK Attr') # pk 속성이 없을 수도 있으므로 getattr 사용
            instance_type = type(self.instance)

        print(f"AttachmentForm __init__ called. Instance: {self.instance}, Instance Type: {instance_type}, Instance PK: {instance_pk}")

        if self.instance and hasattr(self.instance, 'pk') and self.instance.pk: # pk 존재 여부 명시적 확인
            self.fields['file'].required = False
            print(f"  Set file.required to False for instance PK: {self.instance.pk}")
        else:
            print(f"  File.required remains default. Current: {self.fields['file'].required if 'file' in self.fields else 'File field not found'}")

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
        # 'attached_file' 필드 제거 -> Attachment 모델과 인라인 폼셋으로 관리
        fields = ['categories', 'title', 'content']

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '제목을 입력해 주세요.'
            }),
            'content': TinyMCE(attrs={
                'rows': 15,
            }),
        }
        labels = {
            'title': '',
            'content': '',
        }

    # 카테고리 초기값 설정을 위해 __init__ 수정 (문제 3-1 관련)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk: # 수정 폼일 경우
            # 초기 카테고리 값 설정 (뷰에서 전달된 instance의 categories)
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
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '댓글을 입력하세요...'}),
        }
        labels = {
            'content': '', # 댓글 폼 레이블 숨김
        }