# FLO/flo_exam/pdf_utils.py

from io import BytesIO
from django.http import HttpResponse
from django.conf import settings # 프로젝트 설정을 가져오기 위해
import os # 파일 경로 작업을 위해

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, KeepInFrame, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors 
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- 한글 폰트 등록 ---
# 이 부분은 애플리케이션이 처음 로드될 때 한 번만 실행되도록 하는 것이 좋습니다.
# (예: Django 앱의 AppConfig의 ready() 메소드 또는 이 파일 최상단)
# 여기서는 이 파일이 임포트될 때 실행되도록 합니다.

# 실제 폰트 파일 경로를 설정해야 합니다.
# 프로젝트 루트의 static/fonts/ 폴더에 폰트 파일이 있다고 가정합니다.
FONT_DIR = os.path.join(settings.BASE_DIR, 'static', 'fonts') # settings.BASE_DIR 사용
REGULAR_FONT_PATH = os.path.join(FONT_DIR, 'NanumGothic.ttf')  # 예시: 나눔고딕 Regular
BOLD_FONT_PATH = os.path.join(FONT_DIR, 'NanumGothicBold.ttf') # 예시: 나눔고딕 Bold

# ReportLab에 폰트 등록 (폰트 이름은 코드에서 사용할 이름)
try:
    if os.path.exists(REGULAR_FONT_PATH) and os.path.exists(BOLD_FONT_PATH):
        pdfmetrics.registerFont(TTFont('NanumGothic', REGULAR_FONT_PATH))
        pdfmetrics.registerFont(TTFont('NanumGothicBold', BOLD_FONT_PATH))
        DEFAULT_FONT_REGULAR = 'NanumGothic'
        DEFAULT_FONT_BOLD = 'NanumGothicBold'
        print("pdf_utils.py: 나눔고딕 폰트가 성공적으로 등록되었습니다.")
    else:
        # 폰트 파일이 없으면 기본 폰트 사용 (한글 깨짐 발생)
        print("="*50)
        print("경고 (pdf_utils.py): 나눔고딕 폰트 파일을 찾을 수 없습니다.")
        print(f"  Regular 경로 시도: {REGULAR_FONT_PATH}")
        print(f"  Bold 경로 시도: {BOLD_FONT_PATH}")
        print("  프로젝트 내 static/fonts/ 폴더에 NanumGothic.ttf, NanumGothicBold.ttf 파일을 넣어주세요.")
        print("  또는, 시스템에 설치된 다른 한글 폰트 경로로 수정하세요.")
        print("  현재 기본 PDF 폰트(Helvetica)로 진행되며, 한글이 깨질 수 있습니다.")
        print("="*50)
        DEFAULT_FONT_REGULAR = 'Helvetica'
        DEFAULT_FONT_BOLD = 'Helvetica-Bold'
except Exception as e:
    print(f"pdf_utils.py: 폰트 등록 중 오류 발생 - {e}. 기본 폰트로 진행합니다.")
    DEFAULT_FONT_REGULAR = 'Helvetica'
    DEFAULT_FONT_BOLD = 'Helvetica-Bold'
# -------------------------

def escape_text_for_reportlab(text_content):
    """
    ReportLab Paragraph에 사용될 텍스트를 준비합니다.
    줄바꿈은 <br/>로 변경하고, & 문자는 &로 변경합니다.
    다른 <, > 문자는 ReportLab의 태그 파서가 처리하도록 그대로 둡니다.
    AI는 ReportLab이 지원하는 태그(<b>, <i>, <sup>, <sub>, <font>, <a href>)만 사용해야 합니다.
    """
    if text_content is None:
        return ""
    text_to_process = str(text_content)
    # 1. '&'는 HTML 엔티티 '&'로 변경 (다른 엔티티와의 충돌 방지)
    text_to_process = text_to_process.replace("&", "&")
    # 2. '<'와 '>'는 ReportLab의 태그 파싱을 위해 그대로 둡니다.
    # 3. 줄바꿈 문자를 <br/> 태그로 변경
    return text_to_process.replace('\n', '<br/>')


def build_pdf_story(title_text, questions_data, include_answers=False, frame_width=None, frame_height=None):
    """PDF에 들어갈 내용(story)을 생성하는 함수"""
    story = []
    styles = getSampleStyleSheet()

    # 커스텀 스타일 정의 (등록된 폰트 사용)
    style_h1 = ParagraphStyle(name='PDF_H1', parent=styles['h1'], fontName=DEFAULT_FONT_BOLD, fontSize=18, alignment=1, spaceAfter=1*cm)
    style_h2 = ParagraphStyle(name='PDF_H2', parent=styles['h2'], fontName=DEFAULT_FONT_BOLD, fontSize=12, spaceBefore=0.5*cm, spaceAfter=0.2*cm)
    style_normal = ParagraphStyle(name='PDF_Normal', parent=styles['Normal'], fontName=DEFAULT_FONT_REGULAR, fontSize=10, leading=14)
    style_option = ParagraphStyle(name='PDF_Option', parent=style_normal, leftIndent=0.5*cm)
    style_correct_answer = ParagraphStyle(name='PDF_CorrectAnswer', parent=style_normal, fontName=DEFAULT_FONT_BOLD, textColor=colors.HexColor('#007bff'))
    style_explanation_title = ParagraphStyle(name='PDF_ExplanationTitle', parent=style_h2, fontSize=10, spaceBefore=0.3*cm, spaceAfter=0.1*cm)
    style_explanation = ParagraphStyle(name='PDF_Explanation', parent=style_normal, leftIndent=0.5*cm, firstLineIndent=0)

    story.append(Paragraph(escape_text_for_reportlab(title_text), style_h1))

    actual_frame_width = frame_width if frame_width is not None else (21*cm - 4*cm) 
    actual_frame_height = frame_height if frame_height is not None else (29.7*cm - 5*cm)

    for index, q_obj in enumerate(questions_data):
        question_block_content = [] 

        if index > 0:
            line_data = [['']]
            table_line = Table(line_data, colWidths=[17*cm], rowHeights=[0.02*cm]) # 매우 얇은 행
            table_line.setStyle(TableStyle([
                ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.lightgrey), # 아래쪽 선
            ]))
            question_block_content.append(table_line)
            question_block_content.append(Spacer(1, 0.2*cm))
        
        # 문제 번호
        question_block_content.append(Paragraph(escape_text_for_reportlab(f"문제 {q_obj.question_number}."), style_h2))

        if q_obj.question_text:
            question_block_content.append(Paragraph(escape_text_for_reportlab(q_obj.question_text), style_normal))
        question_block_content.append(Spacer(1, 0.2*cm)) # 내용과 선택지 사이 간격s

        if q_obj.question_type == "multiple_choice" and q_obj.options_list:
            for i, option_text in enumerate(q_obj.options_list):
                question_block_content.append(Paragraph(escape_text_for_reportlab(f"({i+1}) {option_text}"), style_option))
            question_block_content.append(Spacer(1, 0.1*cm))
        elif q_obj.question_type == "short_answer" and not include_answers:
            question_block_content.append(Paragraph(escape_text_for_reportlab("답: ____________________"), style_option))
        
        
        if include_answers:
            question_block_content.append(Spacer(1, 0.3*cm))
            question_block_content.append(Paragraph(escape_text_for_reportlab(f"정답: {q_obj.correct_answer}"), style_correct_answer))
            if q_obj.explanation:
                question_block_content.append(Paragraph(escape_text_for_reportlab("해설:"), style_explanation_title))
                question_block_content.append(Paragraph(escape_text_for_reportlab(q_obj.explanation), style_explanation))

        #story.append(KeepInFrame(actual_frame_width, actual_frame_height, question_block_content))
        story.append(KeepTogether(question_block_content))
        story.append(Spacer(1, 0.1*cm)) # 각 문제 블록(KeepInFrame) 사이의 최소 간격

    return story

# 페이지 테두리 및 페이지 번호 등을 그리는 콜백 함수
def my_page_layout(canvas, doc):
    canvas.saveState()
    
    # 1. 페이지 테두리 그리기
    border_margin_x = doc.leftMargin - 0.5*cm # 내용 여백보다 0.5cm 바깥
    border_margin_y = doc.bottomMargin - 0.5*cm
    page_width_with_border_allowance = doc.width + 1*cm
    page_height_with_border_allowance = doc.height + 1*cm
    
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.5) # 선 두께
    canvas.rect(border_margin_x, border_margin_y, 
                page_width_with_border_allowance, page_height_with_border_allowance, 
                stroke=1, fill=0)

    # 2. 페이지 번호 그리기 (선택 사항)
    page_num_text = f"- {doc.page} -"
    canvas.setFont(DEFAULT_FONT_REGULAR, 9)
    canvas.drawCentredString(A4[0] / 2, 1.5*cm, page_num_text) # 페이지 하단 중앙

    canvas.restoreState()

def render_to_pdf_reportlab(filename_prefix, title_text, questions_data, include_answers=False):
    buffer = BytesIO()
    
    # 문서 템플릿 생성 (여백 등 설정)
    doc = BaseDocTemplate(buffer, 
                          pagesize=A4,
                          leftMargin=2.5*cm, rightMargin=2.5*cm, # 내용 영역 여백
                          topMargin=2.5*cm, bottomMargin=2.5*cm, # 내용 영역 여백
                          title=f"{filename_prefix} - {title_text}")
    
    # 프레임 정의 (내용이 그려질 영역)
    # Frame의 크기는 BaseDocTemplate의 여백을 제외한 실제 가용 영역
    main_content_frame = Frame(doc.leftMargin, doc.bottomMargin,
                               doc.width, doc.height, 
                               id='main_content_frame')
    
    # 페이지 템플릿에 프레임과 콜백 함수(페이지 레이아웃용) 연결
    main_page_template = PageTemplate(id='main_page', 
                                      frames=[main_content_frame], 
                                      onPage=my_page_layout) # 모든 페이지에 적용
    
    doc.addPageTemplates([main_page_template])

    # PDF에 들어갈 내용(story) 생성 (프레임 크기 전달)
    story = build_pdf_story(title_text, questions_data, include_answers,
                            frame_width=main_content_frame._width, 
                            frame_height=main_content_frame._height
                           )
    
    try:
        doc.build(story) # story를 사용하여 PDF 문서 빌드
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
    except Exception as e:
        print(f"pdf_utils.py: ReportLab PDF 빌드 중 오류 발생: {e}")
        import traceback
        traceback.print_exc() # 오류 발생 시 상세 Traceback 출력
        buffer.close()
        return None
