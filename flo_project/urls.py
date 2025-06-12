<<<<<<< HEAD
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
=======
"""
URL configuration for flo_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from . import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.conf.urls.i18n import i18n_patterns

def home(request):
    return render(request, 'flo/index.html')
    #return render(request, 'mysite/index.html')
    # return HttpResponse("환영합니다. Django Web 입니다.")
    
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),  # 언어 전환 URL 지원
]

urlpatterns += [  # + 꼭 붙이기
    path('', home, name='home'),  # http://localhost:8000/ -> home
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),  # accounts 앱의 URL 추가
    path('tinymce/', include('tinymce.urls')),  # django-tinymce 관리자 페이지용 URL
    path('flo/', include('flo.urls')),
    path('flo_exam/', include('flo_exam.urls', namespace='flo_exam')), # 플로 프로그램 페이지 URL
]

# 이미지는 web 경로를 쓰는데, 이를 허용하겠다.(요청 URL에 이미지를 요청하면 그 이미지를 보여주겠다.)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
>>>>>>> b0590081b1e26a670b5c09461d4acb164dcc58f5
