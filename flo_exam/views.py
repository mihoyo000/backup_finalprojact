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
from .ai_services import extract_text_and_images_from_pdf, generate_questions_via_openai, generate_image_with_dalle
from .pdf_utils import render_to_pdf_reportlab
from django.utils.encoding import uri_to_iri, iri_to_uri
from urllib.parse import quote
import random
import re



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

    # 이전에 생성된 동일한 ExamDocument에 대한 시험 데이터가 있다면 삭제 (항상 새로운 문제 세트 생성)
    GeneratedExam.objects.filter(exam_document=exam_doc).delete() 
    print(f"views.py: 이전 GeneratedExam 데이터 삭제 (ID: {exam_doc.id})")

    try:
        pdf_path = exam_doc.pdf_file.path
        print(f"views.py: PDF 파일 경로 - {pdf_path}")
        
        # 1. PDF에서 텍스트와 이미지 정보(페이지 번호, URL 등)를 함께 추출
        pdf_text, extracted_images_info = extract_text_and_images_from_pdf(pdf_path, exam_doc.id)

        if not pdf_text:
            print(f"views.py: PDF에서 텍스트 추출 실패 (ID: {exam_doc.id})")
            return JsonResponse({'status': 'error', 'message': 'PDF에서 텍스트를 추출할 수 없습니다. 파일 내용을 확인해주세요.'}, status=400)
        print(f"views.py: PDF 텍스트 추출 완료. 추출된 이미지 수: {len(extracted_images_info)} (ID: {exam_doc.id})")

        # 2. ChatCompletion API를 사용하여 텍스트 기반 문제 생성 (AI가 이미지 참조 힌트도 주도록 요청)
        questions_data_list_from_ai = generate_questions_via_openai(
            text_from_pdf=pdf_text, # 페이지 번호 정보가 포함될 수 있는 텍스트
            num_questions_to_generate=exam_doc.num_questions_requested, 
            requested_question_type=exam_doc.question_type_requested, 
            subject_topic=exam_doc.subject_area
        )

        if not questions_data_list_from_ai or not isinstance(questions_data_list_from_ai, list) or not questions_data_list_from_ai:
            print(f"views.py: AI 문제 생성 실패 또는 응답 형식 오류 (ID: {exam_doc.id})")
            return JsonResponse({'status': 'error', 'message': 'AI가 문제를 생성하지 못했거나 응답 형식이 올바르지 않습니다.'}, status=500)
        print(f"views.py: AI 텍스트 문제 {len(questions_data_list_from_ai)}개 생성 완료 (ID: {exam_doc.id})")

        # 데이터베이스에 생성된 시험 및 문제 저장
        generated_exam_instance = GeneratedExam.objects.create(exam_document=exam_doc)
        
        js_questions_data = [] # JavaScript로 최종 전달할 문제 데이터 리스트
        
        # 추출된 PDF 이미지들을 한 번씩만 사용하기 위한 로직 (선택 사항)
        # available_pdf_images = list(extracted_images_info) # 복사본 사용
        # random.shuffle(available_pdf_images) # 순서를 섞어서 다양한 이미지가 선택되도록

        for index, q_data_item_from_ai in enumerate(questions_data_list_from_ai):
            # GeneratedQuestion 모델 객체 생성 및 저장
            question_instance = GeneratedQuestion.objects.create(
                exam=generated_exam_instance,
                question_number=q_data_item_from_ai.get('question_number', index + 1),
                question_text=q_data_item_from_ai.get('question_text', '문제 내용 없음'),
                question_type=q_data_item_from_ai.get('question_type', 'unknown_type'),
                option1=q_data_item_from_ai.get('options')[0] if q_data_item_from_ai.get('options') and isinstance(q_data_item_from_ai.get('options'), list) and len(q_data_item_from_ai.get('options')) > 0 else None,
                option2=q_data_item_from_ai.get('options')[1] if q_data_item_from_ai.get('options') and isinstance(q_data_item_from_ai.get('options'), list) and len(q_data_item_from_ai.get('options')) > 1 else None,
                option3=q_data_item_from_ai.get('options')[2] if q_data_item_from_ai.get('options') and isinstance(q_data_item_from_ai.get('options'), list) and len(q_data_item_from_ai.get('options')) > 2 else None,
                option4=q_data_item_from_ai.get('options')[3] if q_data_item_from_ai.get('options') and isinstance(q_data_item_from_ai.get('options'), list) and len(q_data_item_from_ai.get('options')) > 3 else None,
                correct_answer=str(q_data_item_from_ai.get('correct_answer', '')),
                explanation=q_data_item_from_ai.get('explanation', '')
            )
            
            question_dict_for_js = question_instance.to_dict() # 모델의 to_dict() 사용
            
            # 3. AI가 제공한 이미지 참조 힌트를 바탕으로 PDF에서 추출된 이미지 매칭
            ai_image_hint = q_data_item_from_ai.get("image_reference_hint")
            assigned_image_url_from_pdf = None

            if ai_image_hint and extracted_images_info: # AI 힌트와 추출된 이미지가 모두 있을 경우
                print(f"views.py: 문제 {question_instance.question_number} - AI 이미지 힌트: '{ai_image_hint}'")
                
                hint_page_number = None
                try: # 힌트에서 페이지 번호 추출 (정규식 사용)
                    page_match = re.search(r"page\s*(\d+)", ai_image_hint, re.IGNORECASE)
                    if page_match:
                        hint_page_number = int(page_match.group(1))
                        print(f"views.py: 힌트에서 추출된 페이지 번호: {hint_page_number}")
                except ValueError:
                    print(f"views.py: 힌트에서 페이지 번호 추출 실패 (숫자 변환 오류) - 힌트: {ai_image_hint}")

                # 힌트에 페이지 번호가 있다면 해당 페이지의 이미지 중 하나를 사용
                if hint_page_number:
                    # 해당 페이지의 이미지들 필터링
                    images_on_hinted_page = [img_info for img_info in extracted_images_info if img_info.get('page_number') == hint_page_number]
                    if images_on_hinted_page:
                        # 여기서는 해당 페이지의 첫 번째 이미지를 사용 (또는 랜덤, 또는 힌트의 다른 설명과 매칭)
                        selected_image_info = images_on_hinted_page[0] 
                        assigned_image_url_from_pdf = selected_image_info.get('url')
                        print(f"views.py: 페이지 번호 {hint_page_number} 기반으로 PDF 이미지 선택: {assigned_image_url_from_pdf}")
                        # 만약 선택된 이미지를 다음 문제에서 재사용하지 않으려면 리스트에서 제거
                        # if selected_image_info in available_pdf_images:
                        #    available_pdf_images.remove(selected_image_info)
                
                # (선택적 고급 로직) 페이지 번호 힌트가 없거나 해당 페이지에 이미지가 없다면,
                # 힌트의 다른 텍스트(이미지 설명)와 추출된 이미지의 설명(현재는 placeholder)을 비교하여 매칭 시도
                # 이 부분은 NLP 기술이나 복잡한 문자열 매칭 로직이 필요하여 여기서는 생략합니다.

            if assigned_image_url_from_pdf:
                question_dict_for_js['image_url'] = assigned_image_url_from_pdf
            
            js_questions_data.append(question_dict_for_js)
        
        print(f"views.py: js_questions_data 리스트 구성 완료. 포함된 문제 수: {len(js_questions_data)}")
        
        print("--- views.py: JS로 반환할 최종 questions 데이터 (일부) ---")
        import pprint
        pprint.pprint(js_questions_data[:2]) # 처음 2개 문제 데이터만 출력 (너무 길어지는 것 방지)
        print("-------------------------------------------------")

        return JsonResponse({
            'status': 'completed', 
            'exam_id': generated_exam_instance.id,
            'questions': js_questions_data,
            'exam_document_title': exam_doc.title
        })

    except Exception as e:
        import traceback
        print(f"views.py (ajax_process_pdf_view): 최종 예외 발생 - {type(e).__name__}: {e}")
        traceback.print_exc()
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