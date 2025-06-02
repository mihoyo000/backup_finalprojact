#flo/forms.py
from django import forms
from .models import Post, Comment, Category
from tinymce.widgets import TinyMCE # TinyMCE 위젯

class PostForm(forms.ModelForm):
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all().order_by('name'), # 모든 카테고리, 이름순 정렬
        # ★★★ 위젯은 HTML에서 Select2로 대체되므로, 여기서 CheckboxSelectMultiple을 명시할 필요는 없음
        # widget=forms.SelectMultiple(attrs={'class': 'form-control categories-select2'}), # Select2 적용을 위한 클래스 추가
        widget=forms.SelectMultiple(attrs={'class': 'categories-select2-target'}), # JavaScript에서 선택할 클래스
        required=False,
        label="카테고리 선택 (최대 5개)",
        help_text="게시글과 관련된 카테고리를 최대 5개까지 선택해주세요."
    )
    class Meta:
        model = Post
        fields = ['categories', 'title', 'content', 'attached_file'] # category -> categories

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '제목을 입력해 주세요.'
            }),
            'content': TinyMCE(attrs={
                'rows': 15,
            }),
            'attached_file': forms.ClearableFileInput(attrs={
                'class': 'form-control-file'
            }),
            # 'categories' 위젯은 위에서 직접 정의했거나, 아래 JavaScript로 Select2 등으로 대체 예정
        }

        labels = {
            # 'categories' 레이블은 위에서 직접 설정
            'title': '',
            'content': '',
            'attached_file': '첨부파일', # 필요하다면 레이블 표시
        }

    def clean_categories(self): # 'categories' 필드에 대한 커스텀 유효성 검사
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