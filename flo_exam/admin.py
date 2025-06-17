# flo_exam/admin.py

from django.contrib import admin
from .models import ExamDocument, GeneratedExam, GeneratedQuestion, UserExamSession, UserAnswer

# 1. 업로드된 PDF 문서 (ExamDocument) 어드민 설정
# @admin.register 데코레이터를 사용하면 클래스와 모델을 함께 등록할 수 있어 편리합니다.
@admin.register(ExamDocument)
class ExamDocumentAdmin(admin.ModelAdmin):
    """
    ExamDocument 모델을 어드민 페이지에서 어떻게 보여줄지 설정합니다.
    """
    # 목록 페이지에 보여줄 필드들을 지정합니다. 'author'를 추가해서 바로 볼 수 있게 합니다.
    list_display = ('id', 'title', 'author', 'processing_status', 'uploaded_at')
    
    # 오른쪽에 필터링 기능을 추가할 필드들을 지정합니다.
    list_filter = ('processing_status', 'author')
    
    # 검색창에서 검색할 필드들을 지정합니다. (작성자 아이디로도 검색 가능)
    search_fields = ('title', 'author__username')
    
    # 읽기 전용으로 만들 필드들을 지정합니다. (어드민에서 실수로 수정하는 것을 방지)
    readonly_fields = ('uploaded_at',)


# 2. 나머지 모델들도 간단하게 등록합니다. (데이터 확인용)
#    - 나중에 필요에 따라 위처럼 상세 설정을 추가할 수 있습니다.
admin.site.register(GeneratedExam)
admin.site.register(GeneratedQuestion)
admin.site.register(UserExamSession)
admin.site.register(UserAnswer)