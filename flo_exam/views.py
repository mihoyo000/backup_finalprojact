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
from .ai_services import extract_text_and_images_from_pdf, generate_questions_via_openai
from .pdf_utils import render_to_pdf_reportlab
from django.utils.encoding import uri_to_iri, iri_to_uri
from urllib.parse import quote
import random
import re


#-----------삭제 예정 임시 로그인 뷰-----------------------------------------------------------------------------------------------------------------
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import logout as django_logout # Django의 기본 로그아웃 함수
from django.contrib.auth.models import User # User 모델 사용
from .forms import TempLoginForm # 방금 만든 임시 로그인 폼


def temp_login_view(request):
    if request.method == 'POST':
        form = TempLoginForm(request.POST)
        if form.is_valid():
            user_id = form.cleaned_data['user_id']
            try:
                # 실제 User 모델에서 해당 ID의 사용자를 찾습니다.
                # 만약 이 사용자가 DB에 미리 생성되어 있어야 합니다.
                user = User.objects.get(pk=user_id)
                # 세션에 사용자 ID 저장 (실제 로그인 메커니즘과는 다름)
                request.session['temp_user_id'] = user.id 
                messages.success(request, f"사용자 ID {user.id} ({user.username})로 임시 로그인되었습니다.")
                # 로그인 후 이동할 페이지 (예: PDF 업로드 페이지 또는 홈페이지)
                return redirect(reverse('flo_exam:upload_page')) 
            except User.DoesNotExist:
                messages.error(request, f"사용자 ID {user_id}를 찾을 수 없습니다.")
            except Exception as e:
                messages.error(request, f"임시 로그인 중 오류 발생: {e}")
    else:
        form = TempLoginForm()
    
    # 현재 임시 로그인된 사용자 정보 표시 (선택 사항)
    temp_user_info = None
    if 'temp_user_id' in request.session:
        try:
            logged_in_user = User.objects.get(pk=request.session['temp_user_id'])
            temp_user_info = f"현재 임시 로그인: {logged_in_user.username} (ID: {logged_in_user.id})"
        except User.DoesNotExist:
            del request.session['temp_user_id'] # 유효하지 않은 ID면 세션에서 제거

    return render(request, 'flo_exam/temp_login.html', {'form': form, 'temp_user_info': temp_user_info})

def temp_logout_view(request):
    # Django의 기본 세션 데이터를 건드리지 않고, 우리 임시 세션만 제거
    if 'temp_user_id' in request.session:
        del request.session['temp_user_id']
        messages.success(request, "임시 로그아웃되었습니다.")
    else:
        messages.info(request, "현재 임시 로그인 상태가 아닙니다.")
    # 로그아웃 후 이동할 페이지
    return redirect(reverse('flo_exam:temp_login')) 
    # 또는 return redirect('/')
# --------------------------------

# --- 기존 뷰 함수들에서 request.user 대신 임시 사용자 사용하도록 수정 (예시) ---
# 이 부분은 나중에 실제 request.user로 쉽게 바꿀 수 있도록 준비합니다.
def get_current_temp_user(request):
    """세션에서 임시 사용자 ID를 가져와 User 객체를 반환하거나 None을 반환합니다."""
    if 'temp_user_id' in request.session:
        try:
            return User.objects.get(pk=request.session['temp_user_id'])
        except User.DoesNotExist:
            del request.session['temp_user_id'] # 잘못된 ID면 세션에서 제거
    return None # Django의 request.user가 익명 사용자일 때 User 객체가 아닌 AnonymousUser를 반환하는 것과 유사하게






#----------------여기까지 삭제예정 로그인 뷰------------------------------------------------------------------------------------------------------------

# 1. 초기 PDF 업로드 페이지 뷰
# ==============================================================================
'''
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
'''
#--------------------------------------------------------------------------------------------------------------삭제 예정 코드
def upload_page_view(request):
    current_user = get_current_temp_user(request) # 임시 사용자 가져오기
    # form = PDFUploadForm(user=current_user) # 폼 초기화 시 전달 (기존 로직 활용)
    # ... (나머지 로직에서 request.user 대신 current_user 사용) ...
    # if request.method == 'POST':
    #     form = PDFUploadForm(request.POST, request.FILES, user=current_user)
    #     if form.is_valid():
    #         exam_doc_instance = form.save(commit=False)
    #         if current_user: # 임시 사용자가 있다면 author로 설정
    #             exam_doc_instance.author = current_user
    #         # ...
    # else:
    #     form = PDFUploadForm(user=current_user)
    # context = {'form': form, 'current_user_for_template': current_user} # 템플릿 전달용
    # ...
    # (이전 답변의 upload_page_view를 참고하여 current_user를 사용하도록 수정)
    # 가장 간단하게는, 이전에 request.user.is_authenticated 를 사용하던 곳을
    # if current_user: 로, request.user를 사용하던 곳을 current_user로 바꿉니다.
    
    # 일단은 이전 upload_page_view 코드를 유지하고,
    # author, user 필드 할당 부분만 아래와 같이 수정한다고 가정합니다.
    # 실제로는 form 초기화 시에도 user를 넘겨주는 것이 좋습니다.
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES, user=current_user) # 폼에도 전달
        if form.is_valid():
            exam_doc_instance = form.save(commit=False)
            if current_user: # 임시 사용자가 있다면 author로 설정
                exam_doc_instance.author = current_user
            exam_doc_instance.processing_status = 'PENDING'
            exam_doc_instance.save()
            messages.info(request, f"'{exam_doc_instance.title}'에 대한 문제 생성을 시작합니다.")
            return redirect(reverse('flo_exam:loading_page_entry', args=[exam_doc_instance.id]))
        else:
            messages.error(request, "입력 내용을 다시 확인해주세요.")
    else:
        form = PDFUploadForm(user=current_user) # 폼에도 전달
    
    context = {'form': form, 'current_user_for_template': current_user}
    return render(request, 'flo_exam/upload_page.html', context)                            # 삭제예정코드
#----------------------------------------------------------------------------------------------------------------------------------






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
        pdf_text, extracted_pdf_images_info = extract_text_and_images_from_pdf(pdf_path, exam_doc.id) # 이미지 정보 받음

        if not pdf_text:
            return JsonResponse({'status': 'error', 'message': 'PDF에서 텍스트를 추출할 수 없습니다.'}, status=400)
        print(f"views.py: PDF 텍스트 추출 완료. 추출된 PDF 이미지 수: {len(extracted_pdf_images_info)}")

        questions_data_list_from_ai = generate_questions_via_openai(
            pdf_text, exam_doc.num_questions_requested, 
            exam_doc.question_type_requested, exam_doc.subject_area
        )

        if not questions_data_list_from_ai or not isinstance(questions_data_list_from_ai, list) or not questions_data_list_from_ai:
            return JsonResponse({'status': 'error', 'message': 'AI 문제 생성 실패 또는 형식 오류.'}, status=500)
        print(f"views.py: AI 텍스트 문제 {len(questions_data_list_from_ai)}개 생성 완료.")

        generated_exam_instance = GeneratedExam.objects.create(exam_document=exam_doc)
        js_questions_data = []
        
        # 이미지 배정 카운터 (최대 1~2개 문제에만 이미지 배정하기 위함)
        assigned_image_count = 0
        max_images_to_assign = random.randint(1, 2) # 한 시험당 최대 이미지 포함 문제 수

        for q_data_item_from_ai in questions_data_list_from_ai:
            question_instance = GeneratedQuestion.objects.create(
                exam=generated_exam_instance,
                question_number=q_data_item_from_ai.get('question_number', len(js_questions_data) + 1),
                question_text=q_data_item_from_ai.get('question_text', '내용 없음'),
                question_type=q_data_item_from_ai.get('question_type', 'unknown_type'),
                option1=q_data_item_from_ai.get('options')[0] if q_data_item_from_ai.get('options') and isinstance(q_data_item_from_ai.get('options'), list) and len(q_data_item_from_ai.get('options')) > 0 else None,
                option2=q_data_item_from_ai.get('options')[1] if q_data_item_from_ai.get('options') and isinstance(q_data_item_from_ai.get('options'), list) and len(q_data_item_from_ai.get('options')) > 1 else None,
                option3=q_data_item_from_ai.get('options')[2] if q_data_item_from_ai.get('options') and isinstance(q_data_item_from_ai.get('options'), list) and len(q_data_item_from_ai.get('options')) > 2 else None,
                option4=q_data_item_from_ai.get('options')[3] if q_data_item_from_ai.get('options') and isinstance(q_data_item_from_ai.get('options'), list) and len(q_data_item_from_ai.get('options')) > 3 else None,
                correct_answer=str(q_data_item_from_ai.get('correct_answer', '')),
                explanation=q_data_item_from_ai.get('explanation', '')
            )
            question_dict_for_js = question_instance.to_dict()
            
            pdf_image_hint_obj = q_data_item_from_ai.get("pdf_image_reference_hint")
            assigned_image_url = None

            if assigned_image_count < max_images_to_assign and isinstance(pdf_image_hint_obj, dict) and extracted_pdf_images_info:
                hint_page = pdf_image_hint_obj.get("page_number")
                hint_desc_for_match = pdf_image_hint_obj.get("image_description", "").lower() # API 응답 키가 image_description이라고 가정

                print(f"views.py: 문제 {question_instance.question_number} - AI PDF 이미지 힌트: page={hint_page}, desc='{hint_desc_for_match}'")

                # 매칭 로직 시작
                best_match_image = None
                
                # 1. 페이지 번호가 일치하는 이미지들 필터링
                candidate_images_on_page = []
                if hint_page:
                    candidate_images_on_page = [img for img in extracted_pdf_images_info if img.get('page_number') == hint_page]
                
                if candidate_images_on_page: # 해당 페이지에 이미지가 있다면
                    # 1-1. 설명도 일치하는 이미지 찾기 (간단한 포함 여부)
                    if hint_desc_for_match:
                        for img_info in candidate_images_on_page:
                            if hint_desc_for_match in img_info.get('description',"").lower():
                                best_match_image = img_info
                                break 
                    if not best_match_image: # 설명 매칭 안되면 해당 페이지 첫 이미지
                        best_match_image = candidate_images_on_page[0]
                elif hint_desc_for_match: # 페이지 힌트 없거나 해당 페이지에 이미지 없을때, 전체에서 설명으로만 매칭
                    for img_info in extracted_pdf_images_info:
                         if hint_desc_for_match in img_info.get('description',"").lower():
                            best_match_image = img_info
                            break
                
                if best_match_image:
                    assigned_image_url = best_match_image.get('url')
                    print(f"  PDF 이미지 매칭 성공: {assigned_image_url}")
                    # extracted_pdf_images_info.remove(best_match_image) # 이 이미지는 더 이상 사용 안 함 (중복 방지)
                                                                    # 이 로직은 available_pdf_images를 따로 만들어서 관리해야 더 정확함
                    assigned_image_count += 1
                else:
                    print(f"  힌트에 맞는 PDF 이미지를 찾지 못함.")
            
            if assigned_image_url:
                question_dict_for_js['image_url'] = assigned_image_url
            
            js_questions_data.append(question_dict_for_js)
        
        print(f"views.py: js_questions_data 리스트 구성 완료. 이미지 포함 문제 수: {assigned_image_count}")
        print("--- views.py: JS로 반환할 최종 questions 데이터 (첫 2개) ---")
        import pprint
        pprint.pprint(js_questions_data[:2])
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
    current_user = get_current_temp_user(request) # 임시 사용자 가져오기------------------------------삭제예정코드
    generated_exam = get_object_or_404(GeneratedExam, pk=generated_exam_id)
    
    current_user_session = UserExamSession.objects.create(
        generated_exam=generated_exam,
        user=current_user
    ) #----------------------------------------------------------------------------------------------여기까지 삭제예정 코드
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
    




