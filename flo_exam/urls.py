from django.urls import path
from . import views

app_name = 'flo_exam'

urlpatterns = [
    path('', views.upload_page_view, name='upload_page_root'),
    path('upload/', views.upload_page_view, name='upload_page'),
    path('exam-process/<int:exam_document_id>/', views.loading_page_entry_view, name='loading_page_entry'),
    path('ajax/generate-problems/<int:exam_document_id>/', views.ajax_process_pdf_view, name='ajax_process_pdf'),
    path('ajax/score-exam/<int:generated_exam_id>/', views.ajax_process_scoring_view, name='ajax_process_scoring'),
    path('download/questions/<int:generated_exam_id>/pdf/', views.download_questions_pdf_view, name='download_questions_pdf'),
    path('download/answers/<int:generated_exam_id>/pdf/', views.download_answers_pdf_view, name='download_answers_pdf'),

]