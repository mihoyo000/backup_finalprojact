from django import forms
from .widgets import SubjectAreaWidget

class SubjectAreaField(forms.MultiValueField):
    def __init__(self, choices=(), **kwargs):
        fields = (
            forms.ChoiceField(choices=choices, required=False),
            forms.CharField(required=False),
        )
        self.widget = SubjectAreaWidget(choices=choices)
        super().__init__(fields=fields, require_all_fields=False, **kwargs)

    def compress(self, data_list):
        if data_list:
            selected_value = data_list[0]
            custom_value = data_list[1]

            if custom_value:
                return custom_value
            elif selected_value:
                return selected_value
        return None