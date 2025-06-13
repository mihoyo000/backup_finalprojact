# flo_project/flo_exam/ai_services.py

# ----------------- [1. 모든 Import 문] -----------------
import os
import json
import uuid
import fitz  # PyMuPDF
import openai
from dotenv import load_dotenv
import logging
import traceback

from django.conf import settings

# LangChain 및 Hugging Face 관련
import torch
import faiss
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS as LangChainFAISS
from langchain_huggingface import HuggingFaceEmbeddings
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForCausalLM

# 로거 설정
logger = logging.getLogger(__name__)

# ----------------- [2. OpenAI 클라이언트 초기화] -----------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = None
if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"):
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        logger.info("ai_services.py: OpenAI API 클라이언트가 성공적으로 초기화되었습니다.")
    except Exception as e:
        logger.error(f"ai_services.py: OpenAI API 클라이언트 초기화 중 오류 발생: {e}")
else:
    logger.warning("="*60)
    logger.warning("경고 (ai_services.py): .env 파일 또는 환경 변수에서 유효한 OPENAI_API_KEY를 찾을 수 없습니다.")
    logger.warning("AI 문제 생성은 목업(테스트용) 데이터로 대체됩니다.")
    logger.warning("="*60)


# ----------------- [3. Hugging Face RAG 챗봇 싱글턴 클래스] -----------------
class HuggingFaceRAGChatbot:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(HuggingFaceRAGChatbot, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        logger.info("\n--- [HuggingFaceRAGChatbot] 초기화 시작 ---")
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"[HuggingFaceRAGChatbot] 현재 실행 장치: {self.device}")

        self.gpu_res = None
        if self.device.type == 'cuda':
            try:
                self.gpu_res = faiss.StandardGpuResources()
                logger.info("[HuggingFaceRAGChatbot] FAISS GPU 리소스를 성공적으로 할당했습니다.")
            except Exception as e:
                logger.error(f"[HuggingFaceRAGChatbot] FAISS GPU 리소스 할당 실패: {e}. CPU로 계속 진행합니다.")
                self.device = torch.device("cpu")

        self.embedding_model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        logger.info(f"[HuggingFaceRAGChatbot] 임베딩 모델 로드 중: {self.embedding_model_name}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={'device': self.device.type}
        )
        logger.info("[HuggingFaceRAGChatbot] 임베딩 모델 로드 완료.")

        self.llm_model_name = "google/gemma-1.1-2b-it"
        logger.info(f"[HuggingFaceRAGChatbot] LLM 모델 로드 중: {self.llm_model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.llm_model_name)
        
        # ★★★ 핵심 수정: Gemma 모델에 맞는 AutoModelForCausalLM 클래스 사용 ★★★
        self.model = AutoModelForCausalLM.from_pretrained(
            self.llm_model_name,
            device_map=self.device.type,
            torch_dtype=torch.bfloat16
        )
        logger.info("[HuggingFaceRAGChatbot] LLM 모델 로드 완료.")

        self.vector_stores = {}
        self._initialized = True
        logger.info("--- [HuggingFaceRAGChatbot] 초기화 완료 ---\n")

    def _load_vector_store(self, exam_document_id: int):
        if exam_document_id in self.vector_stores:
            return self.vector_stores[exam_document_id]

        vectorstore_path = os.path.join(settings.MEDIA_ROOT, 'vectorstores', str(exam_document_id))
        if not os.path.exists(vectorstore_path):
            logger.error(f"[HuggingFaceRAGChatbot] Vector Store 경로를 찾을 수 없습니다: {vectorstore_path}")
            return None

        try:
            logger.info(f"[HuggingFaceRAGChatbot] '{vectorstore_path}'에서 FAISS 인덱스(CPU) 로드 중...")
            vector_store = LangChainFAISS.load_local(
                vectorstore_path, 
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            
            if self.device.type == 'cuda' and self.gpu_res:
                logger.info("[HuggingFaceRAGChatbot] FAISS 인덱스를 GPU로 이동 중...")
                vector_store.index = faiss.index_cpu_to_gpu(self.gpu_res, 0, vector_store.index)
            
            self.vector_stores[exam_document_id] = vector_store
            logger.info(f"[HuggingFaceRAGChatbot] Vector Store ID {exam_document_id} 로드 및 캐싱 완료.")
            return vector_store
        except Exception as e:
            logger.error(f"[HuggingFaceRAGChatbot] Vector Store ID {exam_document_id} 로드 실패: {e}")
            logger.error(traceback.format_exc())
            return None

    def ask(self, query: str, exam_document_id: int):
        logger.info(f"RAG `ask` 호출: (Query: '{query}', Doc ID: {exam_document_id})")
        vector_store = self._load_vector_store(exam_document_id)
        if not vector_store:
            return "현재 시험 자료에 대한 지식 베이스를 찾을 수 없습니다. PDF 업로드부터 다시 시도해주세요."

        docs = vector_store.similarity_search(query, k=5)

        # ★★★ 안정성 강화: 검색 결과 유무에 따라 retrieved_text 정의 ★★★
        if docs:
            retrieved_text = "\n\n".join([doc.page_content for doc in docs])
            retrieved_text = retrieved_text[:2500]
            logger.info("="*50)
            logger.info(f"질문 '{query}'에 대해 검색된 상위 문서 조각:")
            for i, doc in enumerate(docs):
                logger.info(f"  - 조각 {i+1}: {doc.page_content[:200]}...")
            logger.info("="*50)
        else:
            retrieved_text = "관련 정보를 찾을 수 없습니다."
            logger.warning("유사한 문서를 찾지 못했습니다.")
        
        messages = [
            {"role": "user", "content": f"""당신은 주어진 '참고 문서'의 내용만을 사용하여 사용자의 '질문'에 대해 답변하는 AI 튜터입니다.
- 답변은 반드시 '참고 문서' 안에 있는 내용에 근거해야 합니다.
- '참고 문서'에 질문과 관련된 내용이 없다면, "제공된 문서에서는 해당 정보를 찾을 수 없습니다."라고만 답변해야 합니다.
- 답변은 완전한 한국어 문장 형태로 친절하게 설명해주세요.

### 참고 문서:
{retrieved_text}

### 질문:
{query}
"""}
        ]
        
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        try:
            input_ids = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            
            outputs = self.model.generate(
                **input_ids,
                max_new_tokens=256,
            )
            
            response = self.tokenizer.decode(outputs[0][input_ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()

            logger.info(f"LLM 생성 답변: {response}")
            return response if response else "죄송합니다. 질문에 대한 답변을 생성할 수 없습니다."
        except Exception as e:
            logger.error(f"[HuggingFaceRAGChatbot] 답변 생성 중 오류 발생: {e}")
            logger.error(traceback.format_exc())
            return "답변을 생성하는 중에 오류가 발생했습니다. 서버 로그를 확인해주세요."

RAG_CHATBOT_INSTANCE = None

def get_rag_chatbot_instance():
    global RAG_CHATBOT_INSTANCE
    if RAG_CHATBOT_INSTANCE is None:
        logger.warning("RAG_CHATBOT_INSTANCE가 None입니다. 즉시 초기화를 시도합니다.")
        RAG_CHATBOT_INSTANCE = HuggingFaceRAGChatbot()
    return RAG_CHATBOT_INSTANCE


# ----------------- [4. PDF 처리 및 Vector Store 생성 함수] -----------------
def extract_text_and_images_from_pdf(pdf_file_path, exam_document_id):
    full_text = ""
    # 이미지 처리는 일단 생략하여 로직을 단순화합니다.
    # extracted_images_info = [] 
    
    # image_save_dir = os.path.join(settings.MEDIA_ROOT, 'pdf_images', str(exam_document_id))
    # os.makedirs(image_save_dir, exist_ok=True)

    try:
        doc = fitz.open(pdf_file_path)
        for page_num in range(len(doc)):
            page_idx = page_num + 1 
            page = doc.load_page(page_num)
            full_text += f"\n--- Page {page_idx} Content Start ---\n"
            full_text += page.get_text("text")
            full_text += f"\n--- Page {page_idx} Content End ---\n"
        doc.close()

        if not full_text.strip():
            logger.warning(f"PDF '{pdf_file_path}'에서 텍스트를 추출하지 못했습니다.")
            return None, []
        return full_text, [] # 이미지 정보는 빈 리스트 반환
    except Exception as e:
        logger.error(f"PDF 처리 중 오류 ({pdf_file_path}): {e}")
        return None, []
    
    
def preprocess_korean_history_pdf_text(text: str) -> str:
    """
    한국사 요약본 PDF처럼 "주제 : 내용" 형식의 텍스트를
    RAG 검색에 더 유리한 완전한 문장 형태로 변환합니다.
    """
    processed_lines = []
    # 텍스트를 줄 단위로 나눕니다.
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # "주제 : 내용" 또는 "주제: 내용" 형식을 찾습니다.
        if ' : ' in line or ':' in line:
            # 콜론(:)을 기준으로 처음 한 번만 나눕니다.
            parts = [p.strip() for p in line.split(':', 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                subject, content = parts
                # 완전한 문장으로 재구성합니다.
                # 예: "고구려 : 5부족 연맹..." -> "고구려의 주요 내용은 5부족 연맹... 입니다."
                new_sentence = f"{subject}의 주요 내용은 '{content}'입니다."
                processed_lines.append(new_sentence)
            else:
                # 콜론이 있지만 형식이 맞지 않으면 원래 줄을 사용합니다.
                processed_lines.append(line)
        else:
            # 콜론이 없는 줄은 그대로 사용합니다.
            processed_lines.append(line)
            
    # 재구성된 문장들을 다시 하나의 텍스트로 합칩니다.
    new_text = "\n".join(processed_lines)
    logger.info("PDF 텍스트 전처리 완료. 원본 길이: %d, 처리 후 길이: %d", len(text), len(new_text))
    return new_text
    

def create_and_save_vectorstore(text_from_pdf, exam_document_id):
    if not text_from_pdf:
        logger.error("Vector Store 생성을 위한 텍스트가 없습니다.")
        return None
    try:
        logger.info(f"Vector Store 생성 시작 (Doc ID: {exam_document_id}).")
        # <<-- 변경점: chunk_size를 줄이고, overlap 비율을 조정합니다 -->>
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,  # 청크 크기를 1000 -> 500으로 줄임
            chunk_overlap=50   # 오버랩도 적절히 조정
        )
        docs = text_splitter.split_text(text_from_pdf)
        
        chatbot_instance = get_rag_chatbot_instance()
        embeddings = chatbot_instance.embeddings
        
        logger.info("FAISS Vector Store 생성 중 (from_texts)...")
        vectorstore = LangChainFAISS.from_texts(docs, embedding=embeddings)
        
        vectorstore_dir = os.path.join(settings.MEDIA_ROOT, 'vectorstores', str(exam_document_id))
        os.makedirs(vectorstore_dir, exist_ok=True)
            
        vectorstore.save_local(vectorstore_dir)
        logger.info(f"Vector Store를 '{vectorstore_dir}' 경로에 성공적으로 저장했습니다.")
        return vectorstore_dir
    except Exception as e:
        logger.error(f"Vector Store 생성 또는 저장 중 오류 발생: {e}")
        logger.error(traceback.format_exc())
        return None


# ----------------- [5. OpenAI 문제 생성 관련 함수들] -----------------
# (기존에 잘 작동하던 코드를 그대로 사용)
def generate_questions_via_openai(text_from_pdf, num_questions_to_generate, requested_question_type, subject_topic):
    """
    OpenAI API (gpt-4o-mini)를 사용하여 문제를 생성합니다.
    성공 시 문제 딕셔너리의 리스트를, 실패 시 목업 문제 리스트를 반환합니다.
    """
    global client
    if not client:
        logger.warning("ai_services.py: OpenAI 클라이언트 없음. 목업 문제 생성.")
        return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)

    ai_question_type_description = "4지선다 객관식" if requested_question_type == "객관식" else "단답형"

    # 기존의 강력한 프롬프트를 그대로 사용합니다.
    prompt_instructions = f"""
    당신은 제공된 PDF 텍스트 내용을 바탕으로 **학습용 연습 문제를 한국어(Korean)로 생성**하는 전문 AI 어시스턴트입니다.
    PDF 텍스트에는 각 페이지 내용 시작과 끝에 "--- Page X Content Start ---" 와 "--- Page X Content End ---" 형식이 포함되어 페이지를 구분합니다.
    생성할 문제의 조건은 다음과 같습니다:
    - 주제: {subject_topic}
    - 문제 유형: {ai_question_type_description}
    - 문항 수: 정확히 {num_questions_to_generate}개
    - **출력 언어: 모든 질문, 선택지, 정답, 해설은 기본적으로 한국어로 작성되어야 합니다.**
      단, PDF 원문에 포함된 **영어 고유명사, 기술 용어, 또는 직접 인용이 필요한 외국어 구문은 번역하지 않고 원문 그대로 사용**해주세요. (예: 'CSS', 'JavaScript', 'Algorithm', '캡슐화(Encapsulation)')

    응답은 "quiz" 키를 가진 JSON 객체여야 하며, 값은 문제 객체들의 리스트입니다.
    각 문제 객체는 다음 키를 포함해야 합니다 (모든 텍스트 값은 한국어를 기본으로 하되, 필요한 경우 원문 외국어 포함):
    - "question_number": (Integer) 문제 번호 (1부터 시작).
    - "question_text": (String) 문제 내용 (한국어, 필요시 원문 외국어 포함).
    - "question_type": (String) "multiple_choice" 또는 "short_answer".
    - "options": (Array of Strings) 객관식일 경우 4개의 한국어 순수 텍스트 선택지. 단답형은 null.
    - "correct_answer": (String) 정답 텍스트.
    - "explanation": (String) 정답에 대한 상세한 해설.
    - "pdf_image_reference_hint": (Object, Optional) 관련 이미지가 없다면 반드시 null 제공.
    
    제공된 PDF 텍스트 내용 (페이지 정보 포함 가능):
    ---
    {text_from_pdf[:4000]} 
    ---
    위 내용을 참고하여 문제를 출제해주세요.
    오직 지정된 JSON 형식으로만 응답하고, 다른 설명은 절대 추가하지 마세요.
    """

    try:
        logger.info(f"ai_services.py: OpenAI API ('gpt-4o-mini') 요청 시작...")
        api_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI assistant that generates educational quizzes in Korean, based on provided text and instructions. Respond strictly in the specified JSON format."},
                {"role": "user", "content": prompt_instructions}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        raw_content = api_response.choices[0].message.content
        logger.info("ai_services.py: OpenAI API 응답 수신 완료.")
        
        # 강력한 JSON 파싱 로직
        cleaned_content = raw_content.strip()
        if cleaned_content.startswith("```json"): cleaned_content = cleaned_content[7:]
        if cleaned_content.endswith("```"): cleaned_content = cleaned_content[:-3]
        
        parsed_api_response = json.loads(cleaned_content.strip())
        
        questions_data = []

        if isinstance(parsed_api_response, dict) and "quiz" in parsed_api_response and isinstance(parsed_api_response["quiz"], list):
            questions_data = parsed_api_response["quiz"]
            logger.info(f"ai_services.py: 'quiz' 키에서 {len(questions_data)}개 문제 데이터 추출 성공.")
        elif isinstance(parsed_api_response, list):
             questions_data = parsed_api_response
             logger.info(f"ai_services.py: API가 직접 리스트 형식으로 {len(questions_data)}개 문제 데이터 반환.")
        else:
            logger.error(f"ai_services.py: OpenAI 응답이 예상한 형식이 아님. (타입: {type(parsed_api_response)})")
            return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)

        if not questions_data or not all(isinstance(q, dict) for q in questions_data):
            logger.error("ai_services.py: 유효한 문제 리스트를 얻지 못함. 목업 데이터 사용.")
            return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)

        logger.info(f"ai_services.py: {len(questions_data)}개 문제 데이터 최종 파싱 성공.")
        return questions_data

    except Exception as e:
        logger.error(f"ai_services.py: generate_questions_via_openai 함수 내 예외 발생: {type(e).__name__} - {e}")
        logger.error(traceback.format_exc())
        return generate_mock_problem_data(num_questions_to_generate, requested_question_type, subject_topic)

def generate_mock_problem_data(num_questions, question_type, subject_topic="N/A"):
    # (기존 코드와 동일)
    logger.info(f"ai_services.py: 목업 문제 생성 시작 - 문항수: {num_questions}, 유형: {question_type}, 주제: {subject_topic}")
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