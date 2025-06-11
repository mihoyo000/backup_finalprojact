import os
import openai # OpenAI 라이브러리
import fitz  # PyMuPDF 라이브러리 (PDF 텍스트 추출용)
import json  # JSON 데이터 처리용
from dotenv import load_dotenv # .env 파일 로드용
from django.conf import settings
import uuid

# 1. 환경 변수 로드 및 OpenAI 클라이언트 초기화
# --------------------------------------------------------------------------
# .env 파일에서 환경 변수를 로드합니다. (프로젝트 루트에 .env 파일이 있어야 함)
# 이 코드는 이 파일이 처음 임포트될 때 실행됩니다.
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI API 클라이언트 객체를 저장할 변수
# 이 변수는 모듈 레벨에 있어서 이 파일 내의 다른 함수들이 접근할 수 있습니다.
client = None

if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"): # API 키가 존재하고 'sk-'로 시작하는지 (기본적인 유효성 검사)
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        print("ai_services.py: OpenAI API 클라이언트가 성공적으로 초기화되었습니다.")
    except Exception as e:
        print(f"ai_services.py: OpenAI API 클라이언트 초기화 중 오류 발생: {e}")
        client = None # 초기화 실패 시 None으로 설정
else:
    print("="*60)
    print("경고 (ai_services.py): .env 파일 또는 환경 변수에서 유효한 OPENAI_API_KEY를 찾을 수 없습니다.")
    print("                       AI 문제 생성은 목업(테스트용) 데이터로 대체됩니다.")
    print("                       프로젝트 루트에 .env 파일을 만들고 OPENAI_API_KEY='sk-실제API키' 형식으로 입력해주세요.")
    print("="*60)
    client = None # 명시적으로 None 할당

# 2. 이미지 생성 함수
# ---------------------------------------------------------------------------

def generate_image_with_dalle(prompt_for_image, n=1, size="256x256"): # DALL-E 2는 256x256, 512x512, 1024x1024 지원
    """DALL-E API를 사용하여 이미지를 생성하고 이미지 URL을 반환합니다."""
    if not client:
        print("ai_services.py: DALL-E 이미지 생성 실패 - OpenAI 클라이언트 없음.")
        return None

    try:
        print(f"ai_services.py: DALL-E 이미지 생성 요청 시작 - 프롬프트: {prompt_for_image[:50]}...")
        response = client.images.generate( # ★★★ DALL-E API 호출 (v1.x 방식) ★★★
            model="dall-e-2",  # 또는 "dall-e-3" (사용 가능 여부 및 비용 확인)
            prompt=prompt_for_image,
            n=n, # 생성할 이미지 개수
            size=size, # 이미지 크기
            response_format="url" # 생성된 이미지의 URL을 받음 (또는 "b64_json"으로 이미지 데이터 직접 받기)
        )
        
        if response.data and len(response.data) > 0:
            image_url = response.data[0].url
            print(f"ai_services.py: DALL-E 이미지 생성 성공 - URL: {image_url}")
            return image_url
        else:
            print("ai_services.py: DALL-E API가 이미지를 반환하지 않았습니다.")
            return None
            
    except openai.APIError as e:
        print(f"ai_services.py: DALL-E API 오류: {e.status_code if hasattr(e, 'status_code') else 'N/A'} - {e.message if hasattr(e, 'message') else str(e)}")
        return None
    except Exception as e:
        import traceback
        print(f"ai_services.py: DALL-E 이미지 생성 중 예측하지 못한 예외: {type(e).__name__} - {e}")
        print(traceback.format_exc())
        return None


# 2. PDF 텍스트 추출 함수
# --------------------------------------------------------------------------
def extract_text_and_images_from_pdf(pdf_file_path, exam_document_id):
    """
    PDF 파일에서 텍스트와 이미지들을 추출합니다.
    텍스트에는 페이지 번호 정보를 포함시키고,
    이미지는 서버의 MEDIA_ROOT에 저장하고, 이미지 정보(URL, 페이지 번호, 임시 설명) 리스트를 반환합니다.
    """
    full_text = ""
    extracted_images_info = [] 
    
    image_save_dir = os.path.join(settings.MEDIA_ROOT, 'pdf_images', str(exam_document_id))
    os.makedirs(image_save_dir, exist_ok=True)

    try:
        doc = fitz.open(pdf_file_path)
        for page_num in range(len(doc)):
            page_idx = page_num + 1 
            page = doc.load_page(page_num)
            full_text += f"\n--- Page {page_idx} Content Start ---\n"
            full_text += page.get_text("text")
            full_text += f"\n--- Page {page_idx} Content End ---\n"
            
            image_list = page.get_images(full=True)
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                image_filename = f"page{page_idx}_img{img_index+1}_{uuid.uuid4().hex[:8]}.{image_ext}"
                image_server_path = os.path.join(image_save_dir, image_filename)
                
                try:
                    with open(image_server_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    
                    image_web_url = os.path.join(settings.MEDIA_URL, 'pdf_images', str(exam_document_id), image_filename).replace("\\", "/")
                    # 이미지에 대한 간단한 설명 (AI가 힌트 생성 시 참고할 수 있도록)
                    # 실제로는 이미지 주변 텍스트나 OCR 등을 통해 더 나은 설명을 생성할 수 있음
                    img_desc_placeholder = f"Image {img_index+1} on page {page_idx} of the PDF."
                    extracted_images_info.append({
                        'page_number': page_idx,
                        'url': image_web_url,
                        'description': img_desc_placeholder 
                    })
                    # print(f"ai_services.py: 이미지 추출 - {image_web_url} (Page: {page_idx})") # 로그는 필요시 활성화
                except Exception as e_save:
                    print(f"ai_services.py: 이미지 파일 저장 실패 ({image_filename}): {e_save}")
        doc.close()
        if not full_text.strip() and not extracted_images_info: # 텍스트도 이미지도 없으면
            print(f"ai_services.py: PDF '{pdf_file_path}'에서 텍스트와 이미지를 모두 추출하지 못했습니다.")
            return None, []
        return full_text, extracted_images_info
    except Exception as e:
        print(f"ai_services.py: PDF 처리 중 오류 ({pdf_file_path}): {e}")
        return None, []

# 3. OpenAI API를 이용한 문제 생성 함수
# --------------------------------------------------------------------------
def generate_questions_via_openai(text_from_pdf, num_questions_to_generate, requested_question_type, subject_topic):
    """
    OpenAI API (gpt-4o-mini)를 사용하여 문제를 생성합니다.
    성공 시 문제 딕셔너리의 리스트를, 실패 시 목업 문제 리스트를 반환합니다.
    """
    global client
    if not client:
        print("ai_services.py: OpenAI 클라이언트 없음. 목업 문제 생성.")
        return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)

    ai_question_type_description = "4지선다 객관식" if requested_question_type == "객관식" else "단답형"

    prompt_instructions = f"""
    당신은 제공된 PDF 텍스트 내용을 바탕으로 학습용 연습 문제를 생성하는 AI 어시스턴트입니다.
    PDF 텍스트에는 "--- Page X Content Start/End ---" 형식으로 페이지 정보가 포함되어 있습니다.
    생성할 문제의 조건은 다음과 같습니다:
    - 주제: {subject_topic}
    - 문제 유형: {ai_question_type_description}
    - 문항 수: 정확히 {num_questions_to_generate}개

    응답은 "quiz" 키를 가진 JSON 객체여야 하며, 값은 문제 객체들의 리스트입니다.
    각 문제 객체는 다음 키를 포함해야 합니다:
    - "question_number": (Integer) 문제 번호 (1부터 시작).
    - "question_text": (String) 문제 내용.
    - "question_type": (String) "multiple_choice" 또는 "short_answer".
    - "options": (Array of Strings) 객관식일 경우 4개의 순수 텍스트 선택지. 단답형은 null. HTML 태그/주석 금지.
    - "correct_answer": (String) 정답 텍스트.
    - "explanation": (String) 해설.
    - "pdf_image_reference_hint": (Object, Optional) 
        만약 이 문제가 **제공된 PDF 텍스트 내의 특정 이미지와 직접적으로 관련**되어야 한다면, 다음 정보를 포함하는 JSON 객체를 여기에 제공해주세요:
        {{
            "page_number": (Integer) 해당 이미지가 위치한 PDF 페이지 번호 (텍스트의 페이지 마커 기준).
            "image_description": (String) 해당 이미지를 식별할 수 있는 간결하고 핵심적인 영어 설명 (예: "diagram of photosynthesis", "portrait of King Sejong", "map of Goryeo Dynasty").
        }}
        이 힌트는 서버에서 PDF에서 추출된 실제 이미지와 문제를 연결하는 데 사용됩니다.
        관련 이미지가 없다면 이 필드 값으로 **반드시 null**을 제공해주세요.
        이 필드는 전체 문제 중 이미지를 활용하는 것이 교육적으로 매우 효과적이라고 판단되는 **약 1~2개의 문제에 대해서만** 제공해주세요. (모든 문제에 제공 X)

    제공된 PDF 텍스트 내용 (페이지 정보 포함):
    ---
    {text_from_pdf[:4000]} 
    ---
    위 내용을 참고하여 문제를 출제해주세요. "pdf_image_reference_hint"는 문제와 매우 밀접한 관련이 있는 PDF 내 이미지가 있을 경우에만 사용해주세요.
    오직 지정된 JSON 형식으로만 응답하고, 다른 설명은 절대 추가하지 마세요.
    """

    try:
        print(f"ai_services.py: OpenAI API ('gpt-4o-mini') 요청 시작...")
        api_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI assistant that generates educational quizzes. Respond strictly in the specified JSON format with a top-level 'quiz' key. If a question refers to an image in the provided PDF text (which includes page markers), provide a 'pdf_image_reference_hint' object with 'page_number' and 'image_description' (in English) for a few highly relevant questions only. Otherwise, the hint should be null."},
                {"role": "user", "content": prompt_instructions}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        raw_content = api_response.choices[0].message.content
        print("ai_services.py: OpenAI API 응답 수신 완료.")
        # ... (JSON 클리닝 및 파싱, 문제 리스트 추출, 유효성 검사는 이전 답변과 동일) ...
        cleaned_content = raw_content.strip()

        if cleaned_content.startswith("```json"): cleaned_content = cleaned_content[7:]
        if cleaned_content.endswith("```"): cleaned_content = cleaned_content[:-3]
        cleaned_content = cleaned_content.strip()
        if cleaned_content.startswith("```"): cleaned_content = cleaned_content[3:] # ``` 만 있는 경우
        if cleaned_content.endswith("```"): cleaned_content = cleaned_content[:-3]
        cleaned_content = cleaned_content.strip()

        parsed_api_response = json.loads(cleaned_content)
        
        questions_data = []

        if isinstance(parsed_api_response, dict) and "quiz" in parsed_api_response and isinstance(parsed_api_response["quiz"], list):
            questions_data = parsed_api_response["quiz"]
            print(f"ai_services.py: 'quiz' 키에서 {len(questions_data)}개 문제 데이터 추출 성공.")
        elif isinstance(parsed_api_response, list):
             questions_data = parsed_api_response
             print(f"ai_services.py: API가 직접 리스트 형식으로 {len(questions_data)}개 문제 데이터 반환.")
        else:
            print("ai_services.py: OpenAI 응답이 예상한 형식이 아님. (parsed_api_response 타입:", type(parsed_api_response), ")")
            # 이 경우 questions_data는 빈 리스트로 유지됩니다.

        if not questions_data or not all(isinstance(q, dict) for q in questions_data): # questions_data가 비었거나, 내부 항목이 딕셔너리가 아니면
            print("ai_services.py: 유효한 문제 리스트를 얻지 못함. 목업 데이터 사용.")
            return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)

        print(f"ai_services.py: {len(questions_data)}개 문제 데이터 최종 파싱 성공.")
        return questions_data

    except Exception as e: # 모든 예외를 더 구체적으로 잡거나, 마지막에 포괄적으로 처리
        import traceback
        print(f"ai_services.py: generate_questions_via_openai 함수 내 예외 발생: {type(e).__name__} - {e}")
        print(traceback.format_exc())
        return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)


# 4. 목업(테스트용) 문제 생성 함수
# --------------------------------------------------------------------------
def generate_mock_problem_data(num_questions, question_type, subject_topic="N/A"):
    """
    API 호출 실패 또는 테스트 목적으로 사용할 가짜 문제 데이터를 생성합니다.
    """
    print(f"ai_services.py: 목업 문제 생성 시작 - 문항수: {num_questions}, 유형: {question_type}, 주제: {subject_topic}")
    mock_problems = []
    api_question_type = "multiple_choice" if question_type == "객관식" else "short_answer"
    
    for i in range(1, int(num_questions) + 1):
        mock_options = [f"목업 선택지 {j} (문제 {i})" for j in range(1, 5)] if api_question_type == "multiple_choice" else None
        mock_correct_answer = f"목업 선택지 1 (문제 {i})" if api_question_type == "multiple_choice" else f"목업 단답형 정답 {i}"
        
        mock_problems.append({
            "question_number": i,
            "question_text": f"이것은 '{subject_topic}' 주제에 대한 {question_type} 목업 문제 {i}입니다. (AI 연결 실패 또는 테스트용)",
            "question_type": api_question_type,
            "options": mock_options,
            "correct_answer": mock_correct_answer,
            "explanation": f"이것은 문제 {i}에 대한 목업 해설입니다. 실제 내용과는 무관할 수 있습니다."
        })
    return mock_problems