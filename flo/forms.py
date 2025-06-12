#flo/forms.py
from django import forms
from .models import Post, Attachment, Comment, Category
from tinymce.widgets import TinyMCE

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
            instance_pk = getattr(self.instance, 'pk', 'No PK Attr')
            instance_type = type(self.instance)

        print(f"AttachmentForm __init__ called. Instance: {self.instance}, Instance Type: {instance_type}, Instance PK: {instance_pk}")

        if self.instance and hasattr(self.instance, 'pk') and self.instance.pk:
            self.fields['file'].required = False
            print(f"  Set file.required to False for instance PK: {self.instance.pk}")
        else:
            print(f"  File.required remains default. Current: {self.fields['file'].required if 'file' in self.fields else 'File field not found'}")

class PostForm(forms.ModelForm):
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all().order_by('name'),
        widget=forms.MultipleHiddenInput(attrs={'class': 'categories-hidden-inputs'}),
        required=True,
        label="카테고리 선택 (최소 1개, 최대 5개)",
        help_text="게시글과 관련된 카테고리를 최소 1개, 최대 5개까지 선택해주세요."
    )

    class Meta:
        model = Post
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['categories'].initial = self.instance.categories.all()

    def clean_categories(self):
        selected_categories = self.cleaned_data.get('categories')
        # required=True 때문에 selected_categories가 비어있는 경우는 Django가 이미 처리.
        # 여기서는 최대 개수만 체크.
        if selected_categories and len(selected_categories) > 5:
            raise forms.ValidationError("카테고리는 최대 5개까지만 선택할 수 있습니다.")
        
        # ★★★ 중요: 여기서 selected_categories가 비어있을 때 에러를 발생시키면 안 됩니다. ★★★
        # JS에서 alert를 띄우고 제출을 막는 것이 우선입니다.
        # 만약 JS를 우회하여 제출된 경우, required=True에 의해 Django의 기본 'This field is required.' 메시지가 나올 것입니다.
        # 사용자 정의 메시지를 원한다면 forms.py의 error_messages를 사용하고, JS alert는 보조 수단으로 사용해야 합니다.
        # 지금은 JS alert를 우선하므로, 여기서 추가적인 'required' 관련 에러 발생은 불필요합니다.
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