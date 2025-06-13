# flo_project/flo_exam/apps.py
# from django.apps import AppConfig

# class FloExamConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'flo_exam'

# ----------------------------------------------------------------

# flo_project/flo_exam/apps.py
from django.apps import AppConfig
import logging
import traceback

logger = logging.getLogger(__name__)

class FloExamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'flo_exam'

    def ready(self):
        # 새로 만든 RAG 챗봇 서비스 파일을 import 합니다.
        from . import rag_chatbot
        
        if rag_chatbot.RAG_SERVICE_INSTANCE is None:
            logger.info("Django AppConfig.ready(): RAGChatbotService 인스턴스 초기화를 시작합니다.")
            try:
                # rag_chatbot.py의 전역 변수에 인스턴스를 할당합니다.
                rag_chatbot.RAG_SERVICE_INSTANCE = rag_chatbot.RAGChatbotService()
                logger.info("Django AppConfig.ready(): RAGChatbotService 인스턴스 초기화 완료.")
            except Exception as e:
                logger.error(f"Django AppConfig.ready(): RAGChatbotService 초기화 실패: {e}\n{traceback.format_exc()}")