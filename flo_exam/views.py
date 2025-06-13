import json
import os
import logging

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse                     # HttpResponse는 PDF 다운로드용 (아직 미구현)
from django.views.decorators.http import require_POST, require_GET     # 요청 메소드 제한
from django.urls import reverse                                        # URL 이름으로 실제 URL 생성
from django.contrib import messages                                    # 사용자에게 간단한 메시지 표시
from django.db import transaction                                      # 데이터베이스 작업의 원자성 보장
from django.utils import timezone                                      # 채점 완료 시간 기록 등
from django.templatetags.static import static                          # {% static %}과 동일한 기능 (이미지 경로 생성용)

# 현재 앱의 forms.py 와 models.py, ai_services.py 임포트
from .forms import PDFUploadForm
from .models import ExamDocument, GeneratedExam, GeneratedQuestion, UserExamSession, UserAnswer
from .ai_services import HuggingFaceRAGChatbot, extract_text_and_images_from_pdf, generate_questions_via_openai
from .pdf_utils import render_to_pdf_reportlab
from django.utils.encoding import uri_to_iri, iri_to_uri
from urllib.parse import quote
import random
import re

from .ai_services import (
    extract_text_and_images_from_pdf,
    create_and_save_vectorstore,
    generate_questions_via_openai,
    get_rag_chatbot_instance, # 수정된 부분: 직접 클래스를 임포트하는 대신 헬퍼 함수를 사용
    preprocess_korean_history_pdf_text  # <<-- 새로 만든 함수를 import 합니다.
)

logger = logging.getLogger(__name__)  # 현재 파일(views.py)의 이름을 가진 로거 객체를 생성합니다. 이렇게 하면 Django 설정에 따라 로그가 체계적으로 관리됩니다.

# 1. 초기 PDF 업로드 페이지 뷰
# ==============================================================================

def upload_page_view(request):
    """
    사용자가 PDF 파일을 업로드하고 시험 생성 옵션을 선택하는 페이지를 담당합니다.
    POST 요청 시 폼 유효성 검사 후, ExamDocument를 저장하고 로딩 페이지로 리다이렉트합니다.
    """
    if request.method == 'POST':
        # POST 요청 시: 폼 데이터와 파일 데이터로 PDFUploadForm 인스턴스 생성
        # 로그인 기능 추가 시: user=request.user 전달
        form = PDFUploadForm(request.POST, request.FILES, user=request.user if request.user.is_authenticated else None)
        if form.is_valid(): # 폼 데이터가 유효하면
            exam_doc_instance = form.save(commit=False) # DB에 바로 저장하지 않고 인스턴스만 가져옴
            if request.user.is_authenticated: # 사용자가 로그인했다면 작성자 정보 저장
                exam_doc_instance.author = request.user
            exam_doc_instance.processing_status = 'PENDING' # 초기 처리 상태 설정
            exam_doc_instance.save() # 이제 DB에 저장
            
            # 문제 생성 로딩 페이지로 리다이렉트 (생성된 ExamDocument의 ID 전달)
            messages.info(request, f"'{exam_doc_instance.title}'에 대한 문제 생성을 시작합니다.")
            return redirect(reverse('flo_exam:loading_page_entry', args=[exam_doc_instance.id]))
        else:
            # 폼 데이터가 유효하지 않으면 에러 메시지와 함께 현재 페이지 다시 표시
            messages.error(request, "입력 내용을 다시 확인해주세요.")
    else:
        # GET 요청 시: 빈 PDFUploadForm 인스턴스 생성
        form = PDFUploadForm(user=request.user if request.user.is_authenticated else None)
    
    context = {
        'form': form,
        # 템플릿에서 사용할 다른 변수들 (예: 페이지 제목, 초기 로봇 이미지 등) 추가 가능
    }
    return render(request, 'flo_exam/upload_page.html', context)

# 2. SPA(단일 페이지 애플리케이션) 진입점 및 컨테이너 페이지 뷰
# ==============================================================================
def loading_page_entry_view(request, exam_document_id):
    """
    PDF 업로드 후 리다이렉트되는 페이지. 이 페이지가 SPA의 시작점이 됩니다.
    초기 로딩 UI를 보여주고, JavaScript가 이 페이지 로드 후 AJAX로 문제 생성을 시작하도록
    필요한 정보(exam_document_id 등)를 템플릿에 전달합니다.
    """
    exam_document = get_object_or_404(ExamDocument, pk=exam_document_id)
    
    # 이 뷰는 exam_spa_page.html을 렌더링하며, 이 HTML에는 모든 동적 UI 변경 로직을
    # 담은 JavaScript(exam_spa_logic.js)가 포함됩니다.
    context = {
        'exam_document_id': exam_document_id, # JS에서 문제 생성 요청 시 사용
        'exam_document_title': exam_document.title, # JS에서 UI에 표시 가능
        'page_initial_message': "AI가 PDF를 분석하고 문제를 만들고 있습니다. 잠시만 기다려 주세요...", # JS에서 초기 로딩 메시지로 사용
        'initial_robot_image': '/static/flo_exam/images/robot.png', # JS에서 초기 로봇 이미지로 사용
        
        # JavaScript에서 Django URL을 안전하게 사용하기 위해 미리 생성하여 전달
        'ajax_process_pdf_url': reverse('flo_exam:ajax_process_pdf', args=[exam_document_id]), # exam_document_id 포함
        'ajax_process_scoring_url_template': reverse('flo_exam:ajax_process_scoring', args=[0]), # 0은 JS에서 실제 exam_id로 대체될 플레이스홀더
        'download_questions_pdf_url_template': reverse('flo_exam:download_questions_pdf', args=[0]),
        'download_answers_pdf_url_template': reverse('flo_exam:download_answers_pdf', args=[0]),
        'upload_page_url': reverse('flo_exam:upload_page') # "문제 더 풀기" 등에 사용될 업로드 페이지 URL
    }
    return render(request, 'flo_exam/exam_spa_page.html', context)


# 3. AJAX 요청 처리: PDF 분석 및 AI 문제 생성
# ==============================================================================
@require_POST # 이 뷰는 POST 요청만 허용 (JavaScript의 fetch에서 method: 'POST'로 호출)
@transaction.atomic # 여러 DB 작업이 하나의 단위로 처리되도록 보장
def ajax_process_pdf_view(request, exam_document_id):
    """
    JavaScript(AJAX)로부터 호출되어 PDF 텍스트 및 이미지 추출, 
    OpenAI API 문제 생성 (이미지 참조 힌트 포함 요청),
    문제와 추출된 이미지 매칭, 문제 DB 저장을 수행합니다.
    결과로 생성된 문제 데이터(필요시 이미지 URL 포함)를 JSON 형태로 반환합니다.
    """
    exam_doc = get_object_or_404(ExamDocument, pk=exam_document_id)
    print(f"views.py (ajax_process_pdf_view): ExamDocument ID {exam_doc.id} ('{exam_doc.title}') 처리 시작")
    GeneratedExam.objects.filter(exam_document=exam_doc).delete()

    try:
        pdf_path = exam_doc.pdf_file.path
        
        logger.info(f"views.py (ajax_process_pdf_view): ExamDocument ID {exam_doc.id} 처리 시작")
        pdf_text, _ = extract_text_and_images_from_pdf(pdf_path, exam_doc.id)
        
        if not pdf_text:
            return JsonResponse({'status': 'error', 'message': 'PDF에서 텍스트를 추출할 수 없습니다.'}, status=400)
        
        # <<-- 여기서 전처리 함수를 호출합니다! -->>
        processed_pdf_text = preprocess_korean_history_pdf_text(pdf_text)
        
        # 가공된 텍스트로 Vector Store를 생성합니다.
        create_and_save_vectorstore(processed_pdf_text, exam_doc.id)
        
        # OpenAI에 문제를 요청할 때는 가공되지 않은 원본 텍스트를 사용할 수도 있습니다.
        # (AI는 키워드 요약본을 더 잘 이해할 수도 있기 때문)
        questions_data_list_from_ai = generate_questions_via_openai(
            pdf_text, # 원본 텍스트 사용
            exam_doc.num_questions_requested, 
            exam_doc.question_type_requested, 
            exam_doc.subject_area
        )

        if not questions_data_list_from_ai or not isinstance(questions_data_list_from_ai, list):
            logger.error("AI 문제 생성 실패 또는 형식 오류.")
            return JsonResponse({'status': 'error', 'message': 'AI 문제 생성 실패 또는 형식 오류.'}, status=500)

        # 2. DB에 쓰는 작업만 트랜잭션으로 묶기
        js_questions_data = []
        generated_exam_instance = None
        with transaction.atomic():
            # 기존 시험 데이터가 있다면 삭제
            GeneratedExam.objects.filter(exam_document=exam_doc).delete()
            
            # 새 시험 세트 생성
            generated_exam_instance = GeneratedExam.objects.create(exam_document=exam_doc)

            for q_data_item_from_ai in questions_data_list_from_ai:
                question_instance = GeneratedQuestion.objects.create(
                    exam=generated_exam_instance,
                    question_number=q_data_item_from_ai.get('question_number', 0),
                    question_text=q_data_item_from_ai.get('question_text', ''),
                    question_type=q_data_item_from_ai.get('question_type', 'unknown'),
                    option1=q_data_item_from_ai.get('options')[0] if q_data_item_from_ai.get('options') and len(q_data_item_from_ai.get('options')) > 0 else None,
                    option2=q_data_item_from_ai.get('options')[1] if q_data_item_from_ai.get('options') and len(q_data_item_from_ai.get('options')) > 1 else None,
                    option3=q_data_item_from_ai.get('options')[2] if q_data_item_from_ai.get('options') and len(q_data_item_from_ai.get('options')) > 2 else None,
                    option4=q_data_item_from_ai.get('options')[3] if q_data_item_from_ai.get('options') and len(q_data_item_from_ai.get('options')) > 3 else None,
                    correct_answer=str(q_data_item_from_ai.get('correct_answer', '')),
                    explanation=q_data_item_from_ai.get('explanation', '')
                )
                js_questions_data.append(question_instance.to_dict())
        
        logger.info(f"views.py: DB 저장 완료. JS로 반환할 최종 데이터 구성.")
        return JsonResponse({
            'status': 'completed', 
            'exam_id': generated_exam_instance.id if generated_exam_instance else 0,
            'questions': js_questions_data,
            'exam_document_title': exam_doc.title
        })

    except Exception as e:
        import traceback
        # ★★★ 디버깅 print문 5 ★★★
        print(f"--- [DEBUG] CRITICAL ERROR: ajax_process_pdf_view 함수 전체에서 예외 발생! ---")
        print(f"--- [DEBUG] 오류 타입: {type(e).__name__}, 오류 메시지: {e} ---")
        traceback.print_exc()
        print("------------------------------------------------------------------")
        return JsonResponse({'status': 'error', 'message': f'문제 생성 중 예측하지 못한 서버 오류가 발생했습니다.'}, status=500)

# 4. AJAX 요청 처리: 답안 채점
# ==============================================================================
@require_POST
@transaction.atomic
def ajax_process_scoring_view(request, generated_exam_id):
    """
    JavaScript(AJAX)로부터 사용자의 답안을 받아 채점하고 결과를 JSON으로 반환합니다.
    """
    generated_exam = get_object_or_404(GeneratedExam, pk=generated_exam_id)
    print(f"views.py (ajax_process_scoring_view): Exam ID {generated_exam_id} 채점 시작")
    
    # 새 UserExamSession 생성 (또는 기존 세션 이어하기 로직 추가 가능)
    current_user_session = UserExamSession.objects.create(
        generated_exam=generated_exam,
        user=request.user if request.user.is_authenticated else None # 로그인 시 사용자 연결
    )

    questions_in_exam = generated_exam.questions.all().order_by('question_number')
    num_correct = 0
    num_total_questions = questions_in_exam.count()
    js_user_answers_details = [] # JavaScript로 보낼 상세 결과

    for question_instance in questions_in_exam:
        # JavaScript에서 보낸 폼 데이터의 name은 'answer_q_<question_id>' 형식이어야 함
        submitted_answer_text = request.POST.get(f'answer_q_{question_instance.id}', '').strip()
        is_answer_correct = False
        
        # 채점 로직 (단순 문자열 비교, 실제로는 더 정교한 비교 필요 가능성)
        if submitted_answer_text.lower() == question_instance.correct_answer.strip().lower():
            is_answer_correct = True
            num_correct += 1
        
        user_answer_record = UserAnswer.objects.create(
            session=current_user_session,
            question=question_instance,
            submitted_answer=submitted_answer_text,
            is_correct=is_answer_correct
        )
        js_user_answers_details.append(user_answer_record.to_dict_with_question()) # 모델의 to_dict... 메소드

    # 점수 계산 및 세션 정보 업데이트
    final_score = (num_correct / num_total_questions) * 100 if num_total_questions > 0 else 0
    current_user_session.score = final_score
    current_user_session.end_time = timezone.now()
    current_user_session.save()

    # "Flo 한마디" 생성 로직
    flo_message = "수고하셨습니다! 결과를 확인해보세요."
    if final_score >= 80: flo_message = "정말 대단해요! 거의 모든 문제를 맞추셨네요! 🏆"
    elif final_score >= 50: flo_message = "좋아요! 조금만 더 집중하면 더 좋은 결과를 얻을 수 있을 거예요. 💪"
    else: flo_message = "괜찮아요, 다음 기회에 더 잘할 수 있어요! 꾸준히 노력하는 것이 중요합니다. 📖"
    
    print(f"views.py (ajax_process_scoring_view): 채점 완료, 점수: {final_score}")
    return JsonResponse({
        'status': 'completed',
        'session_id': current_user_session.id, # 결과 페이지 등에서 사용 가능
        'results': {
            'exam_id': generated_exam.id, # PDF 다운로드 등에 사용
            'exam_title': generated_exam.exam_document.title,
            'total_questions': num_total_questions,
            'correct_answers_count': num_correct,
            'score': final_score,
            'flo_comment': flo_message,
            'user_answers_details': js_user_answers_details # 각 문제별 상세 결과
        }
    })


# 5. PDF 다운로드 뷰
# ==============================================================================
@require_GET
def download_questions_pdf_view(request, generated_exam_id):
    generated_exam = get_object_or_404(GeneratedExam, pk=generated_exam_id)
    questions = generated_exam.questions.all().order_by('question_number')
    
    filename_prefix = generated_exam.exam_document.title # 파일명에 사용될 접두사
    pdf_title_text = f"{filename_prefix} - 문제지" # PDF 내부 제목
    
    pdf_content = render_to_pdf_reportlab(
        filename_prefix=filename_prefix, # ReportLab 버전에서는 사용되지 않지만, 일관성 위해 남겨둘 수 있음
        title_text=pdf_title_text, 
        questions_data=questions, 
        include_answers=False 
    )

    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        # ... (Content-Disposition 설정은 이전과 동일) ...
        filename = f"{filename_prefix}_문제.pdf"
        safe_filename = quote(filename.replace(' ', '_'))
        response['Content-Disposition'] = f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}'
        return response
    else:
        # ... (에러 처리) ...
        return HttpResponse("문제지 PDF 생성에 실패했습니다 (ReportLab).", status=500)

@require_GET
def download_answers_pdf_view(request, generated_exam_id):
    generated_exam = get_object_or_404(GeneratedExam, pk=generated_exam_id)
    questions = generated_exam.questions.all().order_by('question_number')

    filename_prefix = generated_exam.exam_document.title
    pdf_title_text = f"{filename_prefix} - 답지 및 해설"

    pdf_content = render_to_pdf_reportlab(
        filename_prefix=filename_prefix,
        title_text=pdf_title_text,
        questions_data=questions,
        include_answers=True
    )
    
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        # ... (Content-Disposition 설정은 이전과 동일) ...
        filename = f"{filename_prefix}_답지_해설.pdf"
        safe_filename = quote(filename.replace(' ', '_'))
        response['Content-Disposition'] = f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}'
        return response
    else:
        # ... (에러 처리) ...
        return HttpResponse("답지/해설 PDF 생성에 실패했습니다 (ReportLab).", status=500)
    

# 7. 임시 오답노트/챗봇 테스트 페이지 뷰 (★★★★★ 새 테스트용 뷰)
# ==============================================================================
@require_GET
def mistake_note_page_view(request, exam_document_id):
    """
    챗봇 기능을 테스트하기 위한 임시 오답노트 페이지.
    실제 오답노트 페이지가 완성되면 이 뷰의 로직과 템플릿을 통합합니다.
    """
    exam_doc = get_object_or_404(ExamDocument, pk=exam_document_id)
    
    context = {
        'page_title': f"'{exam_doc.title}' 오답노트",
        'exam_document_id': exam_document_id, # JS에서 챗봇 API 호출 시 필요
        'chatbot_ajax_url': reverse('flo_exam:ajax_chatbot', args=[exam_document_id]),
    }
    return render(request, 'flo_exam/mistake_note_page.html', context)

@require_POST
def ajax_chatbot_view(request, exam_document_id):
    """
    Hugging Face 기반 RAG 챗봇으로 답변을 생성하고 JSON으로 반환합니다.
    """
    try:
        data = json.loads(request.body)
        user_question = data.get('question')
        if not user_question:
            return JsonResponse({'status': 'error', 'answer': '질문이 없습니다.'}, status=400)

        # 수정된 부분: 싱글턴 인스턴스를 가져옵니다.
        chatbot = get_rag_chatbot_instance()
        
        if chatbot is None:
            # 이 경우는 모델 로딩에 실패한 경우입니다.
            return JsonResponse({'status': 'error', 'answer': '챗봇 서비스를 현재 사용할 수 없습니다. 서버 관리자에게 문의하세요.'}, status=503)

        # 챗봇에게 질문하고 답변 받기
        ai_answer = chatbot.ask(user_question, exam_document_id)

        # 참고: 대화 기록을 유지하는 로직은 나중에 추가할 수 있습니다.
        # 지금은 단일 질문/답변만 처리합니다.

        return JsonResponse({'status': 'success', 'answer': ai_answer})

    except Exception as e:
        import traceback
        print(f"views.py (ajax_chatbot_view): 챗봇 처리 중 오류 발생 - {e}")
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'answer': '챗봇 응답 중 서버 오류가 발생했습니다.'}, status=500)