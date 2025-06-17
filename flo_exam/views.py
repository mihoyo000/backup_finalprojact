# /flo_exam/views.py (최종 정리 버전)

import json
import logging
from urllib.parse import quote
import traceback

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.urls import reverse
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from .forms import PDFUploadForm
from .models import ExamDocument, GeneratedExam, GeneratedQuestion, UserExamSession, UserAnswer
from .pdf_utils import render_to_pdf_reportlab

# --- 수정된 import 문: 각 파일에서 필요한 함수만 명확하게 가져옵니다 ---
from .ai_services import extract_text_and_images_from_pdf, generate_questions_via_openai
from .rag_chatbot import get_rag_service_instance

logger = logging.getLogger(__name__)

# 1. 초기 PDF 업로드 페이지 뷰
# ==============================================================================
def upload_page_view(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES, user=request.user if request.user.is_authenticated else None)
        if form.is_valid():
            exam_doc_instance = form.save(commit=False)
            if request.user.is_authenticated:
                exam_doc_instance.author = request.user
            exam_doc_instance.save()
            messages.info(request, f"'{exam_doc_instance.title}'에 대한 문제 생성을 시작합니다.")
            return redirect(reverse('flo_exam:loading_page_entry', args=[exam_doc_instance.id]))
        else:
            messages.error(request, "입력 내용을 다시 확인해주세요.")
    else:
        form = PDFUploadForm(user=request.user if request.user.is_authenticated else None)
    
    context = {'form': form}
    return render(request, 'flo_exam/upload_page.html', context)

# 2. SPA 진입점 뷰
# ==============================================================================
def loading_page_entry_view(request, exam_document_id):
    exam_document = get_object_or_404(ExamDocument, pk=exam_document_id)

    # ★★★★★★★★★★ 마이페이지 다시풀기 모드 25/06/16 ★★★★★★★★★★
    is_retake = request.GET.get('retake') == 'true'
    initial_questions_json = "null"

    if is_retake:
        try:
            # exam_document에 연결된 generated_exam 객체를 직접 조회
            generated_exam = exam_document.generated_exam
            questions = generated_exam.questions.all().order_by('question_number')
            
            if questions.exists(): # 문제가 하나라도 있을 때만 JSON 생성
                js_questions_data = [q.to_dict() for q in questions]
                initial_questions_json = json.dumps({
                    'status': 'completed', 
                    'exam_id': generated_exam.id,
                    'questions': js_questions_data,
                    'exam_document_title': exam_document.title
                })
        except GeneratedExam.DoesNotExist:
            # 연결된 시험이 없는 경우 (예: 생성 실패) 조용히 새로 만들기 모드로 전환
            pass
    # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

    context = {
        'exam_document_id': exam_document_id,
        'exam_document_title': exam_document.title,
        'page_initial_message': "FLO가 PDF를 분석하고 문제를 만들고 있습니다. 잠시만 기다려 주세요...",
        'initial_robot_image': '/static/flo_exam/images/robot.png', # static 경로 수정
        'ajax_process_pdf_url': reverse('flo_exam:ajax_process_pdf', args=[exam_document_id]),
        'ajax_process_scoring_url_template': reverse('flo_exam:ajax_process_scoring', args=[0]),
        'download_questions_pdf_url_template': reverse('flo_exam:download_questions_pdf', args=[0]),
        'download_answers_pdf_url_template': reverse('flo_exam:download_answers_pdf', args=[0]),
        'upload_page_url': reverse('flo_exam:upload_page'),
    # ★★★ 마이페이지 다시풀기 모드 25/06/16  ★★★
        'initial_questions_json': initial_questions_json

    }
    return render(request, 'flo_exam/exam_spa_page.html', context)

# 3. AJAX: 문제 생성 및 Vector Store 생성
# ==============================================================================
@require_POST
def ajax_process_pdf_view(request, exam_document_id):
    exam_doc = get_object_or_404(ExamDocument, pk=exam_document_id)
    logger.info(f"views.py (ajax_process_pdf_view): ExamDocument ID {exam_doc.id} 처리 시작")
    
    try:
        # ★★★ 수정: 바뀐 함수 이름으로 호출하고, 두 개의 반환값을 받습니다 ★★★
        # 1. ai_services.py에서 텍스트와 이미지 정보 추출
        pdf_text, extracted_images = extract_text_and_images_from_pdf(
            exam_doc.pdf_file.path, 
            exam_doc.id
        )
        
        # 2. rag_chatbot.py에 Vector Store 생성을 요청
        if pdf_text:
            rag_service = get_rag_service_instance()
            # 이미지 정보는 RAG 챗봇에 직접 전달하지 않으므로 pdf_text만 사용합니다.
            success = rag_service.create_and_cache_vector_store(pdf_text, exam_doc.id)
            if not success:
                logger.error(f"Vector Store 생성에 실패했지만, 문제 생성은 계속합니다 (Doc ID: {exam_doc.id}).")
        else:
            return JsonResponse({'status': 'error', 'message': 'PDF에서 텍스트를 추출할 수 없습니다.'}, status=400)

        # 3. ai_services.py에서 OpenAI로 문제 생성
        # extracted_images 정보를 문제 생성 시 넘겨줄 수 있지만, 현재 프롬프트에는
        # 이미지 정보를 직접 활용하는 부분이 없으므로 pdf_text만 사용합니다.
        questions_data_list_from_ai = generate_questions_via_openai(
            pdf_text,
            exam_doc.num_questions_requested,
            exam_doc.question_type_requested,
            exam_doc.subject_area
        )
        
        if not questions_data_list_from_ai:
            logger.error("AI가 유효한 문제 데이터를 반환하지 않았습니다.")
            return JsonResponse({'status': 'error', 'message': 'AI 문제 생성에 실패했습니다.'}, status=500)

        # 4. 생성된 문제를 DB에 저장 (이 부분은 기존과 동일하게 유지)
        js_questions_data = []
        with transaction.atomic():
            GeneratedExam.objects.filter(exam_document=exam_doc).delete()
            generated_exam_instance = GeneratedExam.objects.create(exam_document=exam_doc)
            for q_data in questions_data_list_from_ai:
                options = q_data.get('options') or []
                question = GeneratedQuestion.objects.create(
                    exam=generated_exam_instance,
                    question_number=q_data.get('question_number', 0),
                    question_text=q_data.get('question_text', ''),
                    question_type=q_data.get('question_type', 'unknown'),
                    option1=options[0] if len(options) > 0 else None,
                    option2=options[1] if len(options) > 1 else None,
                    option3=options[2] if len(options) > 2 else None,
                    option4=options[3] if len(options) > 3 else None,
                    correct_answer=str(q_data.get('correct_answer', '')),
                    explanation=q_data.get('explanation', '')
                )
                js_questions_data.append(question.to_dict())
        
        return JsonResponse({
            'status': 'completed', 
            'exam_id': generated_exam_instance.id,
            'questions': js_questions_data,
            'exam_document_title': exam_doc.title
        })

    except Exception as e:
        logger.error(f"ajax_process_pdf_view에서 치명적 오류: {e}\n{traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': '문제 생성 중 서버 오류가 발생했습니다.'}, status=500)

# 4. AJAX: RAG 챗봇
# ==============================================================================
@require_POST
def ajax_chatbot_view(request, exam_document_id):
    try:
        data = json.loads(request.body)
        user_question = data.get('question')
        if not user_question:
            return JsonResponse({'status': 'error', 'answer': '질문이 없습니다.'}, status=400)

        rag_service = get_rag_service_instance()
        if not rag_service:
            return JsonResponse({'status': 'error', 'answer': '챗봇 서비스를 현재 사용할 수 없습니다.'}, status=503)

        ai_answer = rag_service.ask(user_question, exam_document_id)
        
        return JsonResponse({'status': 'success', 'answer': ai_answer})
    except Exception as e:
        logger.error(f"ajax_chatbot_view에서 오류 발생: {e}\n{traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'answer': '챗봇 응답 중 서버 오류가 발생했습니다.'}, status=500)

# 5. AJAX 요청 처리: 답안 채점
# ==============================================================================
@require_POST
@transaction.atomic
def ajax_process_scoring_view(request, generated_exam_id):
    # (이전과 동일하게 유지)
    generated_exam = get_object_or_404(GeneratedExam, pk=generated_exam_id)
    logger.info(f"views.py (ajax_process_scoring_view): Exam ID {generated_exam_id} 채점 시작")
    current_user_session = UserExamSession.objects.create(generated_exam=generated_exam, user=request.user if request.user.is_authenticated else None)
    questions_in_exam = generated_exam.questions.all().order_by('question_number')
    num_correct = 0
    num_total_questions = questions_in_exam.count()
    js_user_answers_details = []
    for question_instance in questions_in_exam:
        submitted_answer_text = request.POST.get(f'answer_q_{question_instance.id}', '').strip()
        is_answer_correct = (submitted_answer_text.lower() == question_instance.correct_answer.strip().lower())
        if is_answer_correct:
            num_correct += 1
        user_answer_record = UserAnswer.objects.create(session=current_user_session, question=question_instance, submitted_answer=submitted_answer_text, is_correct=is_answer_correct)
        js_user_answers_details.append(user_answer_record.to_dict_with_question())
    final_score = (num_correct / num_total_questions) * 100 if num_total_questions > 0 else 0
    current_user_session.score = final_score
    current_user_session.end_time = timezone.now()
    current_user_session.save()
    if final_score >= 80: flo_message = "정말 대단해요! 거의 모든 문제를 맞추셨네요! 🏆"
    elif final_score >= 50: flo_message = "좋아요! 조금만 더 집중하면 더 좋은 결과를 얻을 수 있을 거예요. 💪"
    else: flo_message = "괜찮아요, 다음 기회에 더 잘할 수 있어요! 꾸준히 노력하는 것이 중요합니다. 📖"
    logger.info(f"views.py (ajax_process_scoring_view): 채점 완료, 점수: {final_score}")
    return JsonResponse({'status': 'completed', 'session_id': current_user_session.id, 'results': {'exam_id': generated_exam.id, 'exam_title': generated_exam.exam_document.title, 'total_questions': num_total_questions, 'correct_answers_count': num_correct, 'score': final_score, 'flo_comment': flo_message, 'user_answers_details': js_user_answers_details}})

# 6. PDF 다운로드 뷰
# ==============================================================================
@require_GET
def download_questions_pdf_view(request, generated_exam_id):
    # (이전과 동일하게 유지)
    generated_exam = get_object_or_404(GeneratedExam, pk=generated_exam_id)
    questions = generated_exam.questions.all().order_by('question_number')
    filename_prefix = generated_exam.exam_document.title
    pdf_title_text = f"{filename_prefix} - 문제지"
    pdf_content = render_to_pdf_reportlab(filename_prefix=filename_prefix, title_text=pdf_title_text, questions_data=questions, include_answers=False)
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"{filename_prefix}_문제.pdf"
        safe_filename = quote(filename.replace(' ', '_'))
        response['Content-Disposition'] = f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}'
        return response
    return HttpResponse("문제지 PDF 생성에 실패했습니다.", status=500)

@require_GET
def download_answers_pdf_view(request, generated_exam_id):
    # (이전과 동일하게 유지)
    generated_exam = get_object_or_404(GeneratedExam, pk=generated_exam_id)
    questions = generated_exam.questions.all().order_by('question_number')
    filename_prefix = generated_exam.exam_document.title
    pdf_title_text = f"{filename_prefix} - 답지 및 해설"
    pdf_content = render_to_pdf_reportlab(filename_prefix=filename_prefix, title_text=pdf_title_text, questions_data=questions, include_answers=True)
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"{filename_prefix}_답지_해설.pdf"
        safe_filename = quote(filename.replace(' ', '_'))
        response['Content-Disposition'] = f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}'
        return response
    return HttpResponse("답지/해설 PDF 생성에 실패했습니다.", status=500)

# 7. 오답노트 페이지 뷰
# ==============================================================================
@require_GET
def mistake_note_page_view(request, exam_document_id):
    exam_doc = get_object_or_404(ExamDocument, pk=exam_document_id)
    context = {
        'page_title': f"'{exam_doc.title}' 오답노트",
        'exam_document_id': exam_document_id,
        'chatbot_ajax_url': reverse('flo_exam:ajax_chatbot', args=[exam_document_id]),
    }
    return render(request, 'flo_exam/mistake_note_page.html', context)