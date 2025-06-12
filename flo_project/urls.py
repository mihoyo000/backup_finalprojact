from django.contrib import admin
from django.http import HttpResponse # 현재 home 뷰에서 사용 안 함
from django.urls import include, path
# from flo_project import settings # 아래 settings를 직접 사용하므로, 명시적으로 from django.conf import settings가 더 일반적
from django.conf import settings # 이렇게 변경하는 것을 권장
from django.conf.urls.static import static
from django.shortcuts import render
# from django.conf.urls.i18n import i18n_patterns # 현재 주석 처리됨

# 이 home 뷰는 현재 urlpatterns에서 주석 처리되어 사용되지 않고 있습니다.
# 만약 루트 URL을 flo 앱에서 처리한다면 이 함수는 필요 없을 수 있습니다.
def home(request):
    return render(request, 'flo/index.html')
    
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += [
     path('', include('flo.urls')),
     path('admin/', admin.site.urls),
]

# 개발 환경에서 MEDIA 파일 서빙
if settings.DEBUG: # settings.DEBUG 조건 추가 (권장)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ... (주석 처리된 i18n_patterns) ...
