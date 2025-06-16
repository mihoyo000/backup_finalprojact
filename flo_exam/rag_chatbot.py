# flo_project/flo_exam/rag_chatbot.py

import os
import logging
import traceback
from typing import List

from django.conf import settings

import torch
import faiss
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS as LangChainFAISS
from langchain_huggingface import HuggingFaceEmbeddings
from transformers import AutoTokenizer, AutoModelForCausalLM

# --- 추가 임포트 ---
from langchain.text_splitter import RecursiveCharacterTextSplitter # 이 부분 추가

logger = logging.getLogger(__name__)

# --- 1. E5 모델의 접두사 규칙을 위한 커스텀 임베딩 클래스 ---
class HuggingFaceE5Embeddings(HuggingFaceEmbeddings):
    def _embed_documents(self, texts: List[str]) -> List[List[float]]:
        # 문서(passage) 임베딩 시 "passage: " 접두사를 붙입니다.
        prefixed_texts = ["passage: " + text for text in texts]
        return super()._embed_documents(prefixed_texts)

    def embed_query(self, text: str) -> List[float]:
        # 질문(query) 임베딩 시 "query: " 접두사를 붙입니다.
        prefixed_text = "query: " + text
        return super().embed_query(prefixed_text)

# --- 2. RAG 챗봇의 핵심 로직을 담당하는 싱글턴 클래스 ---
class RAGChatbotService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RAGChatbotService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        logger.info("\n--- [RAGChatbotService] 초기화 시작 ---")
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"[RAGChatbotService] 현재 실행 장치: {self.device}")

        # 1-1. 임베딩 모델 로드 (가장 강력한 다국어 모델)
        # self.embedding_model_name = "intfloat/multilingual-e5-large-instruct"  # 너무 속도가 느림.
        self.embedding_model_name = "intfloat/multilingual-e5-base"
        logger.info(f"[RAGChatbotService] 임베딩 모델 로드 중: {self.embedding_model_name}")
        self.embeddings = HuggingFaceE5Embeddings( # E5 모델용 커스텀 클래스 사용
            model_name=self.embedding_model_name,
            model_kwargs={'device': self.device.type}
        )
        logger.info("[RAGChatbotService] 임베딩 모델 로드 완료.")

        # 1-2. LLM 로드 (지시 이행 능력이 가장 뛰어난 모델)
        self.llm_model_name = "google/gemma-1.1-2b-it"
        logger.info(f"[RAGChatbotService] LLM 모델 로드 중: {self.llm_model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.llm_model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.llm_model_name,
            device_map="auto",
            torch_dtype=torch.bfloat16
        )
        logger.info("[RAGChatbotService] LLM 모델 로드 완료.")

        self.vector_stores = {} # 메모리 캐시
        self._initialized = True
        logger.info("--- [RAGChatbotService] 초기화 완료 ---\n")
    
    def ask(self, query: str, exam_document_id: int):
        logger.info(f"RAG `ask` 호출: (Query: '{query}', Doc ID: {exam_document_id})")
        vector_store = self._get_vector_store(exam_document_id)
        if not vector_store:
            return "현재 시험 자료에 대한 지식 베이스를 찾을 수 없습니다. PDF 업로드부터 다시 시도해주세요."

        # --- 1. 검색 성능 향상을 위한 질의 확장 (이전 코드 유지) ---
        # (이 부분은 검색 두뇌를 돕는 역할을 합니다)
        # 중요: 질의 확장 프롬프트에 불필요한 서두를 제거하고, 더 명확하게 질문을 생성하도록 지시
        expansion_prompt = f"다음 사용자 질문을 분석하여, 정보 검색에 가장 효과적일 것 같은 검색어 또는 다른 형태의 질문 3가지를 생성해줘. 각 질문은 줄바꿈으로 구분해줘. 기존 질문의 요지를 벗어나지 않아야 해.\n\n사용자 질문: {query}"
        expanded_queries = []
        try:
            expansion_input_ids = self.tokenizer(expansion_prompt, return_tensors="pt").to(self.device)
            expansion_outputs = self.model.generate(**expansion_input_ids, max_new_tokens=100)
            # 불필요한 앞부분 제거
            generated_queries_text = self.tokenizer.decode(expansion_outputs[0][expansion_input_ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
            if generated_queries_text:
                expanded_queries = [q.strip() for q in generated_queries_text.split('\n') if q.strip()]
        except Exception as e:
            logger.error(f"질의 확장 중 오류: {e}")
        
        all_queries = [query] + expanded_queries
        all_retrieved_docs = []
        for q in all_queries:
            # k 값을 늘려 더 많은 문서 조각을 가져오고, 후처리에서 필터링
            retrieved_docs = vector_store.similarity_search(q, k=5) # k=2에서 k=5로 증가
            all_retrieved_docs.extend(retrieved_docs)
        
        unique_docs_dict = {doc.page_content: doc for doc in all_retrieved_docs}
        unique_docs = list(unique_docs_dict.values())
        
        if not unique_docs:
            return "죄송합니다. 참고 문서에서 질문과 관련된 내용을 찾을 수 없습니다."
            
        retrieved_text = "\n".join([doc.page_content for doc in unique_docs])

        # --- 2. 답변 성능 향상을 위한 최종 프롬프트 (가장 최근 대화에서 제안된 수정 사항 포함) ---
        # (이 부분은 답변 두뇌를 훈련시키는 역할을 합니다)
        messages = [
            {"role": "user", "content": f"""
# 역할(Persona):
당신은 'Flo'라는 이름을 가진, 친절하고 지식이 풍부한 AI 오답노트 튜터입니다. 당신의 유일한 임무는 주어진 '참고 문서'의 내용만을 사용하여 사용자의 '질문'에 대해 답변하는 것입니다.

# 핵심 규칙(Core Directive):
- **절대 외부 지식이나 당신의 기존 지식을 사용하지 마세요.** 오직 '참고 문서'만이 당신이 아는 세상의 전부입니다.
- 답변은 항상 완전한 한국어 문장 형태로, 친절하고 상세하게 설명해야 합니다.
- '참고 문서'에 질문에 대한 내용이 조금이라도 없다면, **반드시 "죄송합니다. 제공된 문서에서는 해당 내용에 대한 정보를 찾을 수 없습니다."** 라고만 답변해야 합니다. 다른 말을 덧붙이지 마세요.
- **가장 중요: 사용자의 '질문'에서 요청하는 특정 주제에만 집중하여 답변을 생성해야 합니다.** '참고 문서'에 다른 주제의 내용이 함께 포함되어 있더라도, **질문과 관련 없는 내용은 절대로 답변에 포함하지 마세요.**
- **답변을 시작할 때 '참고 문서에 따르면', '참고 문서에서는', '주어진 문서를 바탕으로', '문서 내용에 의하면'과 같은 표현을 절대로 사용하지 마세요.** 마치 당신이 직접 그 정보를 아는 것처럼 자연스럽고 직접적으로 답변해야 합니다.

# 답변 생성 프로세스 (Step-by-Step):
1.  **[1단계: 질문 주제 파악]** 사용자의 '질문'에서 핵심 주제(예: 동학 농민 봉기, 임오군란, 갑신정변 등)를 명확히 파악합니다.
2.  **[2단계: 관련 정보 추출]** '참고 문서'의 모든 내용을 주의 깊게 읽고, 1단계에서 파악한 **핵심 주제와 직접적으로 관련된 모든 사실, 키워드, 문장만을** 찾아냅니다. 이때, 다른 주제의 내용은 철저히 무시하고 제외합니다.
3.  **[3단계: 답변 생성]** 2단계에서 추출된 정보만을 사용하여, 질문에 대한 완전하고 친절한 답변을 문장 형태로 재구성합니다. **답변은 '참고 문서에 따르면'과 같은 서두 없이 바로 내용을 시작합니다.**
4.  **[4단계: 최종 검토]** 생성된 답변이 '참고 문서'에 없는 내용을 포함하고 있지는 않은지, 그리고 **사용자의 질문 주제 외에 다른 주제의 내용이 전혀 포함되어 있지 않은지** 마지막으로 철저히 확인합니다.

# 예시:
- **예시 1 (성공적인 경우 - 관련 내용만 답변):**
    - 참고 문서: "동학 농민 봉기 : 반봉건, 반외세, 공주 우금치 전투에서 패배, 잔여 병력 항일 운동 참여. 임오군란은 구식군인 차별과 구식군인을 포함한 도시빈민 봉기를 일으키고 흥선대원군을 재집권했습니다."
    - 질문: "동학농민봉기에 대해 알려줘"
    - 올바른 답변: "네, 동학 농민 봉기는 반봉건과 반외세의 성격을 띠었습니다. 봉기는 공주 우금치 전투에서 패배했으나, 잔여 병력이 항일 운동에 참여했습니다."
- **예시 2 (정보가 없는 경우):**
    - 참고 문서: "고구려 : 5부족 연맹"
    - 질문: "동학농민봉기에 대해 알려줘"
    - 올바른 답변: "죄송합니다. 제공된 문서에서는 해당 내용에 대한 정보를 찾을 수 없습니다."

---
### 참고 문서:
{retrieved_text}

### 질문:
{query}
"""}
        ]
        
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        try:
            input_ids = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            # max_new_tokens를 적절히 조절하여 너무 길어지지 않게 합니다.
            outputs = self.model.generate(**input_ids, max_new_tokens=256) 
            response = self.tokenizer.decode(outputs[0][input_ids['input_ids'].shape[1]:], skip_special_tokens=True).strip()
            
            return response if response else "죄송합니다. 답변을 생성하지 못했습니다."
        except Exception as e:
            logger.error(f"답변 생성 중 오류 발생: {e}\n{traceback.format_exc()}")
            return "답변을 생성하는 중에 오류가 발생했습니다."

    def create_and_cache_vector_store(self, text_from_pdf: str, exam_document_id: int):
        """PDF 텍스트로 Vector Store를 생성하고 메모리와 파일에 저장합니다."""
        logger.info(f"Vector Store 생성 및 캐싱 시작 (Doc ID: {exam_document_id}).")
        try:
            # --- 기존 줄 단위 분할 대신, RecursiveCharacterTextSplitter 사용 ---
            # 적절한 chunk_size와 chunk_overlap을 설정하세요.
            # 구분자를 명확히 설정하여 각 사건별로 잘 분리되도록 유도
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,  # 적절한 청크 크기 (예: 500자)
                chunk_overlap=50, # 청크 간 중복 (예: 50자)
                separators=["\n\n", "\n", " ", ""], # 분리 우선순위: 두 줄바꿈 -> 한 줄바꿈 -> 공백 -> 글자 단위
                length_function=len,
                is_separator_regex=False,
            )
            docs = text_splitter.create_documents([text_from_pdf]) # 텍스트를 문서 객체로 분할
            
            if not docs:
                logger.warning("PDF에서 유효한 문서 청크를 찾을 수 없습니다.")
                return False

            vector_store = LangChainFAISS.from_documents(docs, embedding=self.embeddings)
            
            # 파일에 저장
            vectorstore_dir = os.path.join(settings.MEDIA_ROOT, 'vectorstores', str(exam_document_id))
            os.makedirs(vectorstore_dir, exist_ok=True)
            vector_store.save_local(vectorstore_dir)
            logger.info(f"Vector Store를 '{vectorstore_dir}' 경로에 저장했습니다.")
            
            # 메모리에 캐시
            self.vector_stores[exam_document_id] = vector_store
            return True
        except Exception as e:
            logger.error(f"Vector Store 생성 또는 캐싱 중 오류 발생: {e}\n{traceback.format_exc()}")
            return False

    def _get_vector_store(self, exam_document_id: int):
        """메모리 캐시 또는 파일에서 Vector Store를 로드합니다."""
        if exam_document_id in self.vector_stores:
            logger.info(f"메모리 캐시에서 Vector Store (ID: {exam_document_id})를 찾았습니다.")
            return self.vector_stores[exam_document_id]

        vectorstore_path = os.path.join(settings.MEDIA_ROOT, 'vectorstores', str(exam_document_id))
        if not os.path.exists(vectorstore_path):
            logger.warning(f"Vector Store 경로를 찾을 수 없습니다: {vectorstore_path}")
            return None
        
        try:
            logger.info(f"파일에서 Vector Store (ID: {exam_document_id}) 로드 중...")
            
            # <<-- ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★ -->>
            # <<-- ★★★    이 부분이 모든 문제를 해결하는 핵심입니다    ★★★ -->>
            # <<-- ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★ -->>
            # Vector Store를 로드할 때, 파일에 저장된 임베딩 함수 대신
            # 현재 메모리에 있는 'self.embeddings' 객체를 사용하도록 명시적으로 재정의합니다.
            # 이렇게 하면 항상 동일한 임베딩 함수로 검색하게 되어 차원 불일치 오류가 발생하지 않습니다.
            vector_store = LangChainFAISS.load_local(
                vectorstore_path, 
                self.embeddings, # ★★★ 바로 이 부분입니다! ★★★
                allow_dangerous_deserialization=True
            )
            # <<-- ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★ -->>

            self.vector_stores[exam_document_id] = vector_store
            logger.info(f"Vector Store (ID: {exam_document_id})를 성공적으로 로드하고 캐시했습니다.")
            return vector_store
        except Exception as e:
            logger.error(f"파일에서 Vector Store 로드 실패: {e}\n{traceback.format_exc()}")
            return None

    # ask 메서드가 두 번 정의되어 있습니다. 위에 있는 ask 메서드만 남기고 아래 ask 메서드는 제거해야 합니다.
    # 중복된 ask 메서드를 제거하거나, 위에 있는 ask 메서드에 아래 로직을 통합하세요.
    # 예를 들어, 아래 ask 메서드의 내용 (retrieved_docs, messages 구성)을 위에 있는 ask 메서드에 합치세요.
    # 저는 현재 중복된 `ask` 메서드를 제거하고 위에 있는 `ask` 메서드에 통합하는 방향으로 수정했습니다.

# --- 3. Django 앱 시작 시 모델을 로드하기 위한 전역 인스턴스 ---
RAG_SERVICE_INSTANCE = None

def get_rag_service_instance():
    """전역 RAG 서비스 인스턴스를 반환합니다. 앱 시작 시 초기화됩니다."""
    global RAG_SERVICE_INSTANCE
    if RAG_SERVICE_INSTANCE is None:
        logger.warning("RAG_SERVICE_INSTANCE가 None입니다. 즉시 초기화를 시도합니다.")
        RAG_SERVICE_INSTANCE = RAGChatbotService()
    return RAG_SERVICE_INSTANCE