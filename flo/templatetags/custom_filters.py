from django import template
import os

register = template.Library()

@register.filter
def basename(value):
    if hasattr(value, 'name'): # FileField 객체의 경우
        return os.path.basename(value.name)
    elif isinstance(value, str): # 문자열 경로인 경우
        return os.path.basename(value)
    return value

@register.filter
def filename_only(value): # 위 basename과 동일한 기능이므로 하나만 사용해도 됩니다.
    return basename(value)