from django.apps import AppConfig


# class FloExamConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'flo_exam'

# flo_project/flo_exam/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class FloExamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'flo_exam'

    def ready(self):
        """
        Django 앱이 준비되었을 때 호출됩니다.
        서버 시작 시 한 번만 실행되므로, 무거운 모델을 로드하기에 적합합니다.
        """
        # 순환 참조(circular import)를 피하기 위해 ready 메소드 내에서 import 합니다.
        from . import ai_services
        
        # 아직 RAG 챗봇 인스턴스가 생성되지 않았다면, 생성합니다.
        if ai_services.RAG_CHATBOT_INSTANCE is None:
            logger.info("Django AppConfig.ready(): HuggingFaceRAGChatbot 인스턴스 초기화를 시작합니다.")
            try:
                # ai_services 모듈의 전역 변수에 싱글턴 인스턴스를 할당합니다.
                ai_services.RAG_CHATBOT_INSTANCE = ai_services.HuggingFaceRAGChatbot()
                logger.info("Django AppConfig.ready(): HuggingFaceRAGChatbot 인스턴스 초기화 완료.")
            except Exception as e:
                logger.error(f"Django AppConfig.ready(): HuggingFaceRAGChatbot 초기화 실패: {e}")
                # 서버 시작을 막지는 않지만, 에러를 명확히 남깁니다.
                # 챗봇 기능은 작동하지 않을 것입니다.
        else:
            logger.info("Django AppConfig.ready(): HuggingFaceRAGChatbot 인스턴스가 이미 존재합니다.")