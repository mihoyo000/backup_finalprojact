from django import forms

class SubjectAreaWidget(forms.MultiWidget):
    def __init__(self, choices=(), attrs=None):
        widgets = [
            forms.Select(attrs=attrs, choices=choices),
            forms.TextInput(attrs={**(attrs or {}), 'placeholder': '직접 입력 또는 선택 결과 확인'}),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            if isinstance(value, str):
                select_widget_choices = dict(self.widgets[0].choices)
                if value in select_widget_choices:
                    return [value, ''] # 선택지에 있으면 선택지로, 직접 입력은 비움
                else:
                    return ['', value] # 선택지에 없으면 직접 입력으로
            elif isinstance(value, (list, tuple)) and len(value) == 2:
                return value
        return ['', '']
    
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # Select 위젯에 '선택하세요'옵션을 추가하고 싶다면 여기서 조작 가능
        return context