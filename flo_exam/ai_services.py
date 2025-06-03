# FLO/flo_exam/ai_services.py

import os
import openai
import fitz # PyMuPDF
import json
from dotenv import load_dotenv


load_dotenv()

# 환경 변수에서 API 키 가져오기
OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("="*60)
    print("경고: .env 파일 또는 환경 변수에서 OPENAI_API_KEY를 찾을 수 없습니다.")
    print("       AI 문제 생성 기능이 정상적으로 동작하지 않을 수 있으며,")
    print("       목업(테스트용) 문제가 대신 생성될 수 있습니다.")
    print("       프로젝트 루트에 .env 파일을 만들고 OPENAI_API_KEY='sk-...' 형식으로 키를 입력해주세요.")
    print("="*60)
    # API 키가 없으면 openai 라이브러리에 None 또는 빈 문자열을 할당하여
    # 이후 openai.api_key를 체크하는 부분에서 API 호출을 시도하지 않도록 합니다.
    openai.api_key = None
else:
    openai.api_key = OPENAI_API_KEY
    # print("OpenAI API 키가 성공적으로 로드되었습니다.") # 디버깅용


def extract_text_from_pdf(pdf_path):
    """PDF 파일에서 텍스트를 추출합니다."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text("text")
        doc.close()
        if not text.strip():
            print(f"경고: PDF '{pdf_path}'에서 텍스트를 추출하지 못했습니다. 비어있는 내용입니다.")
            return None
        return text
    except Exception as e:
        print(f"PDF 텍스트 추출 오류 ({pdf_path}): {e}")
        return None

def generate_questions_with_openai(pdf_text, num_questions, question_type_requested, subject_area):
    """OpenAI API (gpt-4o-mini)를 사용하여 문제를 생성하고 JSON으로 파싱합니다."""
    if not openai.api_key: # API 키가 설정되지 않았거나 유효하지 않으면 목업 데이터 사용
        print("경고: OpenAI API 키가 설정되지 않았거나 유효하지 않아 목업 문제를 생성합니다.")
        return generate_mock_questions(num_questions, question_type_requested, subject_area)

    prompt_question_type = "4지선다 객관식" if question_type_requested == "객관식" else "단답형"

    prompt = f"""
    당신은 주어진 PDF 내용과 주제를 바탕으로 학습 문제를 생성하는 AI입니다.
    이번 요청은 새로운 문제 세트를 위한 것입니다. 이전에 생성된 문제들과는 다른, 새로운 관점의 문제들을 생성해주세요.
    다음 정보를 사용하여 문제를 생성해주세요:
    - 주제: {subject_area}
    - 문제 유형: {prompt_question_type}
    - 문항 수: {num_questions}개

    각 문제에 대해 다음 키를 포함하는 JSON 객체들의 리스트 형식으로 응답해야 합니다:
    - "question_number": (Integer) 문제 번호 (1부터 시작)
    - "question_text": (String) 문제의 내용
    - "question_type": (String) "multiple_choice" 또는 "short_answer" (요청된 유형과 일치해야 함)
    - "options": (Array of Strings) 객관식 문제의 경우 4개의 선택지 리스트. 단답형의 경우 null 또는 빈 배열.
    - "correct_answer": (String) 정답. 객관식의 경우 4개 선택지 중 하나의 텍스트. 단답형의 경우 정답 문자열.
    - "explanation": (String) 문제에 대한 간략한 해설.

    제공된 PDF 내용 (일부):
    ---
    {pdf_text[:3800]} 
    ---
    위 내용을 우선적으로 참고하여 문제를 출제하되, 내용이 부족하거나 부적절하면 일반적인 '{subject_area}' 주제와 관련된 문제를 출제해도 됩니다.
    반드시 문제, 선택지, 정답, 해설을 모두 포함하여 {num_questions}개의 문제를 생성하고, 지정된 JSON 형식으로만 응답해주세요. 다른 추가적인 설명이나 대화는 포함하지 마세요. 항상 새로운 문제를 생성하도록 노력해주세요.
    """

    try:
        print(f"OpenAI API ({'gpt-4o-mini'}) 요청 시작: {num_questions}개, {question_type_requested}, 주제: {subject_area}")
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI assistant that generates educational quizzes based on provided text and instructions, responding only in the specified JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            # response_format={ "type": "json_object" } # 지원 여부 확인 후 사용
        )
        content = response.choices[0].message.content
        print("OpenAI API 응답 받음.")

        if content.strip().startswith("```json"):
            content_cleaned = content.strip()[7:]
            if content_cleaned.strip().endswith("```"):
                content_cleaned = content_cleaned.strip()[:-3]
            content = content_cleaned
        elif content.strip().startswith("```"):
             content_cleaned = content.strip()[3:]
             if content_cleaned.strip().endswith("```"):
                content_cleaned = content_cleaned.strip()[:-3]
             content = content_cleaned
        
        questions_data = json.loads(content.strip())
        
        if not isinstance(questions_data, list) or not all(isinstance(q, dict) for q in questions_data):
            print("OpenAI 응답 형식이 예상한 리스트가 아님. 목업 데이터 사용.")
            print(f"잘못된 형식의 응답 (일부): {content[:500]}...")
            return generate_mock_questions(num_questions, question_type_requested, subject_area)
        
        if len(questions_data) != num_questions:
            print(f"경고: 요청한 문항 수({num_questions})와 생성된 문항 수({len(questions_data)})가 다릅니다. 응답 일부만 사용하거나 목업 데이터 사용.")
            questions_data = questions_data[:num_questions]
            if not questions_data:
                 return generate_mock_questions(num_questions, question_type_requested, subject_area)

        print(f"{len(questions_data)}개의 문제 데이터 파싱 성공.")
        return questions_data

    except json.JSONDecodeError as e:
        print(f"OpenAI 응답 JSON 파싱 오류: {e}")
        print(f"파싱 시도한 내용 (일부): {content[:500]}...")
        return generate_mock_questions(num_questions, question_type_requested, subject_area)
    except openai.error.OpenAIError as e:
        print(f"OpenAI API 오류: {e}")
        return generate_mock_questions(num_questions, question_type_requested, subject_area)
    except Exception as e:
        print(f"문제 생성 중 알 수 없는 오류: {e}")
        return generate_mock_questions(num_questions, question_type_requested, subject_area)


def generate_mock_questions(num_questions, question_type, subject_area="N/A"):
    """테스트 및 API 실패 시 사용할 목업 문제 데이터 생성"""
    print(f"목업 문제 생성: {num_questions}개, {question_type}, 주제: {subject_area}")
    mock_data = []
    q_type_api = "multiple_choice" if question_type == "객관식" else "short_answer"
    
    for i in range(1, int(num_questions) + 1):
        options = [f"선택지 {j} (문제 {i})" for j in range(1, 5)] if q_type_api == "multiple_choice" else None
        correct_answer_mock = f"선택지 1 (문제 {i})" if q_type_api == "multiple_choice" else f"단답형 정답 {i}"
        
        mock_data.append({
            "question_number": i,
            "question_text": f"이것은 '{subject_area}' 주제의 {question_type} 목업 문제 {i}입니다. AI 연결 실패 또는 테스트용입니다.",
            "question_type": q_type_api,
            "options": options,
            "correct_answer": correct_answer_mock,
            "explanation": f"이것은 문제 {i}에 대한 목업 해설입니다. 실제 내용과 무관합니다."
        })
    return mock_data