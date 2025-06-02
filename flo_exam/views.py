# flo_exam/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import PDFUploadForm
from .models import ExamDocument # 나중에 업로드된 파일 목록을 보여줄 때 필요할 수 있음

def upload_pdf_view(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save() # 데이터베이스에 저장
            messages.success(request, f"'{instance.title}' 파일이 성공적으로 업로드되었습니다.")
            return redirect('upload_pdf') # 성공 후 현재 페이지로 리다이렉트 (또는 다른 페이지)
        else:
            messages.error(request, "업로드에 실패했습니다. 입력 내용을 확인해주세요.")
    else:
        form = PDFUploadForm()

    context = {'form': form}
    return render(request, 'flo_exam/upload_page.html', context)