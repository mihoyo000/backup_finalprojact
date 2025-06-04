import os
import openai # OpenAI 라이브러리
import fitz  # PyMuPDF 라이브러리 (PDF 텍스트 추출용)
import json  # JSON 데이터 처리용
from dotenv import load_dotenv # .env 파일 로드용

# 1. 환경 변수 로드 및 OpenAI 클라이언트 초기화
# --------------------------------------------------------------------------
# .env 파일에서 환경 변수를 로드합니다. (프로젝트 루트에 .env 파일이 있어야 함)
# 이 코드는 이 파일이 처음 임포트될 때 실행됩니다.
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI API 클라이언트 객체를 저장할 변수
# 이 변수는 모듈 레벨에 있어서 이 파일 내의 다른 함수들이 접근할 수 있습니다.
api_client = None

if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"): # API 키가 존재하고 'sk-'로 시작하는지 (기본적인 유효성 검사)
    try:
        api_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        print("ai_services.py: OpenAI API 클라이언트가 성공적으로 초기화되었습니다.")
    except Exception as e:
        print(f"ai_services.py: OpenAI API 클라이언트 초기화 중 오류 발생: {e}")
        api_client = None # 초기화 실패 시 None으로 설정
else:
    print("="*60)
    print("경고 (ai_services.py): .env 파일 또는 환경 변수에서 유효한 OPENAI_API_KEY를 찾을 수 없습니다.")
    print("                       AI 문제 생성은 목업(테스트용) 데이터로 대체됩니다.")
    print("                       프로젝트 루트에 .env 파일을 만들고 OPENAI_API_KEY='sk-실제API키' 형식으로 입력해주세요.")
    print("="*60)
    api_client = None # 명시적으로 None 할당

# 2. PDF 텍스트 추출 함수
# --------------------------------------------------------------------------
def extract_text_from_pdf(pdf_file_path):
    """
    주어진 PDF 파일 경로에서 텍스트 내용을 추출합니다.
    성공 시 텍스트 문자열을, 실패 시 None을 반환합니다.
    """
    try:
        document = fitz.open(pdf_file_path)
        full_text = ""
        for page_num in range(len(document)):
            page = document.load_page(page_num)
            full_text += page.get_text("text") # 순수 텍스트만 추출
        document.close()
        
        if not full_text.strip(): # 추출된 텍스트가 비어있는지 확인
            print(f"ai_services.py: PDF '{pdf_file_path}'에서 텍스트를 추출하지 못했습니다 (내용 없음).")
            return None
        # print(f"ai_services.py: PDF 텍스트 추출 완료 (일부): {full_text[:200]}...") # 디버깅용
        return full_text
    except Exception as e:
        print(f"ai_services.py: PDF 텍스트 추출 중 오류 발생 ({pdf_file_path}): {e}")
        return None

# 3. OpenAI API를 이용한 문제 생성 함수
# --------------------------------------------------------------------------
def generate_questions_via_openai(text_from_pdf, num_questions_to_generate, requested_question_type, subject_topic):
    """
    OpenAI API (gpt-4o-mini)를 사용하여 문제를 생성합니다.
    성공 시 문제 딕셔너리의 리스트를, 실패 시 목업 문제 리스트를 반환합니다.
    """
    global api_client # 모듈 레벨의 api_client 변수를 사용함을 명시 (또는 인자로 전달)

    if not api_client: # API 클라이언트가 유효하지 않으면 목업 데이터 사용
        print("ai_services.py: OpenAI API 클라이언트가 유효하지 않아 목업 문제를 생성합니다.")
        return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)

    # AI에게 전달할 문제 유형 텍스트 준비
    ai_question_type_description = "4지선다 객관식" if requested_question_type == "객관식" else "단답형"

    # AI에게 전달할 프롬프트 (지시문) 작성
    # 이 프롬프트는 문제의 품질과 형식에 매우 큰 영향을 미칩니다.
    prompt_instructions = f"""
    당신은 제공된 텍스트 내용과 주제를 바탕으로 학습용 연습 문제를 생성하는 AI 어시스턴트입니다.
    생성할 문제의 조건은 다음과 같습니다:
    - 주제: {subject_topic}
    - 문제 유형: {ai_question_type_description}
    - 문항 수: 정확히 {num_questions_to_generate}개

    응답은 반드시 다음 구조를 따르는 JSON 객체여야 합니다.
    최상위에는 "quiz"라는 키가 있고, 이 키의 값은 각 문제 정보를 담은 JSON 객체들의 리스트여야 합니다.
    예시: {{"quiz": [{{"question_number": 1, "question_text": "...", ...}}]}}

    각 문제 객체는 다음 키와 값 형식을 가져야 합니다:
    - "question_number": (Integer) 1부터 시작하는 문제 번호.
    - "question_text": (String) 문제의 질문 내용.
    - "question_type": (String) 요청된 문제 유형 ("multiple_choice" 또는 "short_answer").
    - "options": (Array of Strings) "multiple_choice" 유형일 경우, 반드시 4개의 선택지 텍스트를 포함하는 배열. "short_answer" 유형일 경우 null 또는 빈 배열.
                 각 선택지 텍스트는 순수한 일반 문자열이어야 하며, HTML 태그나 주석, 특수 마크업을 절대 포함하지 마세요.            
    - "correct_answer": (String) 정답. "multiple_choice"의 경우 4개 선택지 중 정답 텍스트. "short_answer"의 경우 실제 정답 문자열.
    - "explanation": (String) 문제에 대한 간결한 해설.

    제공된 텍스트 내용 (일부):
    ---
    {text_from_pdf[:3800]} 
    ---
    위 내용을 최우선으로 참고하여 문제를 출제해주세요. 내용이 부족하다면, 일반적인 '{subject_topic}' 관련 문제를 출제해도 좋습니다.
    다른 추가적인 설명이나 대화 없이, 오직 지정된 JSON 형식으로만 응답해주십시오.
    """

    try:
        print(f"ai_services.py: OpenAI API ('gpt-4o-mini') 요청 시작 - 문항수: {num_questions_to_generate}, 유형: {requested_question_type}, 주제: {subject_topic}")
        
        # OpenAI API 호출 (새로운 v1.x 방식)
        api_response = api_client.chat.completions.create(
            model="gpt-4o-mini", # 사용할 AI 모델
            messages=[
                {"role": "system", "content": "You are an AI assistant that generates educational quizzes. Respond strictly in the specified JSON format, with a top-level 'quiz' key containing a list of question objects. Each option text must be plain text without any HTML, comments, or special markup."},
                {"role": "user", "content": prompt_instructions}
            ],
            temperature=0.7, # 결과의 다양성 조절 (0.0 ~ 2.0)
            response_format={"type": "json_object"} # AI가 JSON 형식으로 응답하도록 강제 (지원하는 모델에서만)
        )
        raw_content = api_response.choices[0].message.content
        print("ai_services.py: OpenAI API 응답 수신 완료.")
        # print(f"ai_services.py: API 원본 응답 (앞부분): {raw_content[:300]}...") # 디버깅 시 확인

        # 가끔 응답이 Markdown 코드 블록(```json ... ```)으로 감싸져 올 수 있으므로 제거
        cleaned_content = raw_content.strip()
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:]
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]
        cleaned_content = cleaned_content.strip()

        parsed_api_response = json.loads(cleaned_content) # JSON 문자열을 Python 딕셔너리로 변환

        # API 응답 구조 확인 및 문제 리스트 추출
        if isinstance(parsed_api_response, dict) and "quiz" in parsed_api_response and isinstance(parsed_api_response["quiz"], list):
            generated_problems_list = parsed_api_response["quiz"]
            print(f"ai_services.py: 'quiz' 키에서 {len(generated_problems_list)}개의 문제 데이터 추출 성공.")
        elif isinstance(parsed_api_response, list): # 혹시 바로 리스트로 응답한 경우
             generated_problems_list = parsed_api_response
             print(f"ai_services.py: API가 직접 리스트 형식으로 {len(generated_problems_list)}개 문제 데이터 반환.")
        else:
            print("ai_services.py: OpenAI 응답이 예상한 'quiz' 키를 포함한 객체 또는 리스트 형식이 아님. 목업 데이터 사용.")
            print(f"ai_services.py: 잘못된 형식의 응답 (일부): {str(parsed_api_response)[:500]}...")
            return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)

        # 문제 리스트 내부 유효성 검사 (각 항목이 딕셔너리인지)
        if not all(isinstance(problem, dict) for problem in generated_problems_list):
            print("ai_services.py: 'quiz' 리스트 내의 일부 항목이 딕셔너리 형식이 아님. 목업 데이터 사용.")
            return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)
        
        # 요청한 문항 수와 실제 생성된 문항 수 확인
        if not generated_problems_list:
            print("ai_services.py: AI가 문제를 생성하지 못했습니다 (빈 리스트 반환). 목업 데이터 사용.")
            return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)
        
        # (선택적) 문항 수가 다를 경우 처리 (여기서는 일단 생성된 만큼만 반환하거나, 엄격하게는 목업으로)
        # if len(generated_problems_list) != num_questions_to_generate:
        #     print(f"ai_services.py: 경고 - 요청 문항 수({num_questions_to_generate})와 생성된 문항 수({len(generated_problems_list)}) 불일치.")
            # generated_problems_list = generated_problems_list[:num_questions_to_generate] # 생성된 만큼만 잘라서 사용

        print(f"ai_services.py: {len(generated_problems_list)}개의 문제 데이터 최종 파싱 및 반환 준비 완료.")
        return generated_problems_list

    except json.JSONDecodeError as e:
        print(f"ai_services.py: OpenAI 응답 JSON 파싱 중 오류 발생: {e}")
        if 'raw_content' in locals(): # raw_content 변수가 정의되어 있다면 출력
             print(f"ai_services.py: 파싱 시도한 원본 내용 (일부): {raw_content[:500]}...")
        return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)
    except openai.APIError as e: # OpenAI 라이브러리 자체의 API 오류 처리
        print(f"ai_services.py: OpenAI API 호출 중 오류 발생: 상태 코드 {e.status_code if hasattr(e, 'status_code') else 'N/A'} - {e.message if hasattr(e, 'message') else str(e)}")
        return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)
    except Exception as e: # 그 외 모든 예외 처리
        import traceback
        print(f"ai_services.py: 문제 생성 중 예측하지 못한 예외 발생: {type(e).__name__} - {e}")
        print(traceback.format_exc()) # 상세한 오류 경로 출력
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