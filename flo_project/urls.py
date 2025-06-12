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
    return render(request, 'mysite/index.html')
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
]

# 이미지는 web 경로를 쓰는데, 이를 허용하겠다.(요청 URL에 이미지를 요청하면 그 이미지를 보여주겠다.)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # 개발 환경에서 MEDIA_URL을 통해 MEDIA_ROOT의 파일들을 서빙하도록 설정

# urlpatterns += i18n_patterns(
#     path('multilang/', include('multilang.urls')),
# )