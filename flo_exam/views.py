from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.urls import reverse
from django.contrib import messages
from django.db import transaction # 데이터베이스 트랜잭션 처리
from django.utils import timezone

from .forms import PDFUploadForm
from .models import ExamDocument, GeneratedExam, GeneratedQuestion
from .ai_services import extract_text_from_pdf, generate_questions_with_openai

# 1. PDF 업로드 페이지
def upload_page_view(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES, user=request.user if request.user.is_authenticated else None)
        if form.is_valid():
            exam_doc_instance = form.save(commit=False)
            if request.user.is_authenticated:
                exam_doc_instance.author = request.user
            exam_doc_instance.processing_status = 'PENDING'
            exam_doc_instance.save()
            # ★★★ 로딩 페이지로 exam_document_id와 함께 리다이렉트 ★★★
            return redirect(reverse('flo_exam:loading_page_entry', args=[exam_doc_instance.id]))
        else:
            messages.error(request, "입력 내용을 확인해주세요.")
    else:
        form = PDFUploadForm(user=request.user if request.user.is_authenticated else None)
    
    context = {'form': form}
    return render(request, 'flo_exam/upload_page.html', context)


# 2. 로딩 페이지 진입점 (이 페이지가 SPA의 시작)
def loading_page_entry_view(request, exam_document_id):
    exam_document = get_object_or_404(ExamDocument, pk=exam_document_id)

    form_instance = PDFUploadForm(user=request.user if request.user.is_authenticated else None) 
    
    # 이 페이지는 초기 로딩 UI를 보여주고, JS가 AJAX로 문제 생성을 시작하도록 유도
    context = {
        'exam_document_id': exam_document_id,
        'exam_document_title': exam_document.title, # JS에서 사용 가능
        'page_initial_message': "AI가 PDF를 분석하고 문제를 만들고 있습니다. 잠시만 기다려 주세요...",
        'initial_robot_image': '/static/flo_exam/images/robot.png', # 문제 생성 중 로봇
        'form': form_instance,
        
        # JavaScript에서 사용할 URL들을 context로 전달
        'ajax_process_pdf_url': reverse('flo_exam:ajax_process_pdf', args=[exam_document_id]),
        'ajax_process_scoring_url_template': reverse('flo_exam:ajax_process_scoring', args=[0]), # 0은 JS에서 exam_id로 대체
        'download_questions_pdf_url_template': reverse('flo_exam:download_questions_pdf', args=[0]),
        'download_answers_pdf_url_template': reverse('flo_exam:download_answers_pdf', args=[0]),
        'upload_page_url': reverse('flo_exam:upload_page') # "문제 더 풀기" 등에 사용
    }
    # 이 템플릿이 이제 SPA의 컨테이너가 됨
    return render(request, 'flo_exam/exam_spa_page.html', context) 


# 3. AJAX: PDF 처리 및 문제 생성 (이전 ajax_process_pdf_view와 유사)
@require_POST
@transaction.atomic
def ajax_process_pdf_view(request, exam_document_id): # exam_document_id를 URL에서 받음
    exam_doc = get_object_or_404(ExamDocument, pk=exam_document_id)

    # 중복 처리 방지 (선택 사항이나 권장)
    if GeneratedExam.objects.filter(exam_document=exam_doc).exists():
        existing_exam = GeneratedExam.objects.get(exam_document=exam_doc)
        GeneratedExam.objects.filter(exam_document=exam_doc).delete()

    # exam_doc.processing_status = 'PROCESSING' # 상태 업데이트
    # exam_doc.save()
    try:
        pdf_path = exam_doc.pdf_file.path
        pdf_text = extract_text_from_pdf(pdf_path)
        if not pdf_text:
            # exam_doc.processing_status = 'FAILED'
            # exam_doc.save()
            return JsonResponse({'status': 'error', 'message': 'PDF에서 텍스트를 추출할 수 없습니다.'}, status=400)

        questions_data_list = generate_questions_with_openai(
            pdf_text,
            exam_doc.num_questions_requested,
            exam_doc.question_type_requested,
            exam_doc.subject_area
        )

        if not questions_data_list or not isinstance(questions_data_list, list) or not questions_data_list:
            # exam_doc.processing_status = 'FAILED'
            # exam_doc.save()
            return JsonResponse({'status': 'error', 'message': 'AI가 문제를 생성하지 못했습니다.'}, status=500)

        generated_exam = GeneratedExam.objects.create(exam_document=exam_doc)
        processed_questions = []
        for q_data in questions_data_list:
            question_obj = GeneratedQuestion.objects.create(
                exam=generated_exam,
                question_number=q_data.get('question_number', 0),
                question_text=q_data.get('question_text', '내용 없음'),
                question_type=q_data.get('question_type', 'unknown'),
                option1=q_data.get('options')[0] if q_data.get('options') and len(q_data.get('options')) > 0 else None,
                option2=q_data.get('options')[1] if q_data.get('options') and len(q_data.get('options')) > 1 else None,
                option3=q_data.get('options')[2] if q_data.get('options') and len(q_data.get('options')) > 2 else None,
                option4=q_data.get('options')[3] if q_data.get('options') and len(q_data.get('options')) > 3 else None,
                correct_answer=str(q_data.get('correct_answer', '')),
                explanation=q_data.get('explanation', '')
            )
            processed_questions.append(question_obj.to_dict()) # JS로 전달할 데이터 (정답/해설 포함 안 함)
        
        # exam_doc.processing_status = 'COMPLETED'
        # exam_doc.save()
        return JsonResponse({
            'status': 'completed', 
            'exam_id': generated_exam.id, 
            'questions': processed_questions, # 문제 목록 (JS가 UI 생성용)
            'exam_document_title': exam_doc.title
        })
    except Exception as e:
        # exam_doc.processing_status = 'FAILED'
        # exam_doc.save()
        return JsonResponse({'status': 'error', 'message': f'문제 생성 중 서버 오류: {str(e)}'}, status=500)

# 4. AJAX: 답안 채점 (이전 ajax_process_scoring_view와 유사)
@require_POST
@transaction.atomic
def ajax_process_scoring_view(request, generated_exam_id):
    # ... (이전 답변의 ajax_process_scoring_view 로직과 거의 동일) ...
    # UserExamSession 생성 시 user=request.user (로그인 시) 또는 null 처리
    # 응답 JSON에 결과 데이터 포함
    generated_exam = get_object_or_404(GeneratedExam, pk=generated_exam_id)
    
    user_exam_session = UserExamSession.objects.create(
        generated_exam=generated_exam,
        user=request.user if request.user.is_authenticated else None
    )

    questions_in_exam = generated_exam.questions.all().order_by('question_number')
    correct_count = 0
    total_questions_count = questions_in_exam.count()
    user_answers_details_for_js = []

    for q_obj in questions_in_exam: # 변수명 변경 q -> q_obj
        submitted_answer_str = request.POST.get(f'answer_q_{q_obj.id}', '').strip() # 폼 네임 일치 중요
        is_correct_flag = False
        
        if submitted_answer_str.lower() == q_obj.correct_answer.strip().lower(): # 대소문자 구분 없이 비교
            is_correct_flag = True
            correct_count += 1
        
        user_answer_obj = UserAnswer.objects.create(
            session=user_exam_session,
            question=q_obj,
            submitted_answer=submitted_answer_str,
            is_correct=is_correct_flag
        )
        user_answers_details_for_js.append(user_answer_obj.to_dict_with_question())

    score_value = (correct_count / total_questions_count) * 100 if total_questions_count > 0 else 0
    user_exam_session.score = score_value
    user_exam_session.end_time = timezone.now()
    user_exam_session.save()

    flo_comment_text = "결과를 확인해주세요." # ... (점수별 코멘트 로직) ...

    return JsonResponse({
        'status': 'completed',
        'session_id': user_exam_session.id,
        'results': {
            'exam_id': generated_exam.id,
            'exam_title': generated_exam.exam_document.title,
            'total_questions': total_questions_count,
            'correct_answers_count': correct_count,
            'score': score_value,
            'flo_comment': flo_comment_text,
            'user_answers_details': user_answers_details_for_js # 각 문제 정답, 해설, 사용자 답 포함
        }
    })


# 5. PDF 다운로드 뷰들 (이전과 동일)
@require_GET
def download_questions_pdf_view(request, generated_exam_id):
    # ... (PDF 생성 및 HttpResponse 반환 로직) ...
    return HttpResponse(f"문제 PDF 다운로드 (Exam ID: {generated_exam_id}) - 구현 예정")

@require_GET
def download_answers_pdf_view(request, generated_exam_id):
    # ... (PDF 생성 및 HttpResponse 반환 로직) ...
    return HttpResponse(f"답지/해설 PDF 다운로드 (Exam ID: {generated_exam_id}) - 구현 예정")
