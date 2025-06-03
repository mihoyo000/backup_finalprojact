// FLO/flo_exam/static/flo_exam/js/exam_spa_logic.js
document.addEventListener('DOMContentLoaded', function() {
    console.log("exam_spa_logic.js: DOM Content Loaded");

    // HTML에서 전달된 전역 변수 사용 (존재 여부 확인)
    if (typeof EXAM_DOCUMENT_ID === 'undefined' ||
        typeof EXAM_DOCUMENT_TITLE === 'undefined' ||
        typeof PAGE_INITIAL_MESSAGE === 'undefined' ||
        typeof APP_URLS === 'undefined' ||
        typeof STATIC_PATHS === 'undefined') {
        console.error("exam_spa_logic.js: 필요한 전역 변수가 HTML 템플릿에서 제대로 전달되지 않았습니다.");
        alert("페이지 초기화에 필요한 정보가 부족합니다. 이전 페이지로 돌아가거나 관리자에게 문의하세요.");
        return; // 필수 변수가 없으면 실행 중단
    }
    console.log("exam_spa_logic.js: 전역 변수 확인 완료");

    const dynamicContentArea = document.getElementById('dynamic-content-area');
    const robotImage = document.getElementById('robot-image');

    // HTML <template> 태그에서 UI 조각 가져오기
    const loadingUITemplateHTML = document.getElementById('loading-ui-template-spa')?.innerHTML;
    const solveExamUITemplateHTML = document.getElementById('solve-exam-ui-template-spa')?.innerHTML;
    const resultUITemplateHTML = document.getElementById('exam-result-ui-template-spa')?.innerHTML;

    let currentGeneratedExamId = null; // 생성된 시험의 ID (채점 및 PDF 다운로드 시 사용)

    // --- UI 렌더링 함수들 ---
    function showInitialLoading() {
        console.log("exam_spa_logic.js: showInitialLoading 호출됨");
        if (loadingUITemplateHTML && dynamicContentArea && robotImage) {
            dynamicContentArea.innerHTML = loadingUITemplateHTML;
            dynamicContentArea.querySelector('.loading-text').textContent = PAGE_INITIAL_MESSAGE;
            robotImage.src = STATIC_PATHS.robotGenerating;
        } else {
            console.error("exam_spa_logic.js: 로딩 UI 템플릿 또는 필수 DOM 요소를 찾을 수 없습니다.");
            if (dynamicContentArea) {
                dynamicContentArea.innerHTML = `<p class="text-center py-5">${PAGE_INITIAL_MESSAGE}<br><span class="spinner-border text-primary mt-2"></span></p>`;
            }
            if (robotImage) robotImage.src = STATIC_PATHS.robotGenerating;
        }
    }
    
    function showGenericLoading(message, robotStateKey = "robotGenerating") {
        console.log(`exam_spa_logic.js: showGenericLoading 호출됨 - 메시지: ${message}, 로봇상태: ${robotStateKey}`);
        if (loadingUITemplateHTML && dynamicContentArea && robotImage) {
            dynamicContentArea.innerHTML = loadingUITemplateHTML;
            dynamicContentArea.querySelector('.loading-text').textContent = message;
            robotImage.src = STATIC_PATHS[robotStateKey] || STATIC_PATHS.robotGenerating;
        } else {
            console.error("exam_spa_logic.js: 로딩 UI 템플릿 또는 필수 DOM 요소를 찾을 수 없습니다.");
            if (dynamicContentArea) {
                dynamicContentArea.innerHTML = `<p class="text-center py-5">${message}<br><span class="spinner-border text-primary mt-2"></span></p>`;
            }
            if (robotImage) robotImage.src = STATIC_PATHS[robotStateKey] || STATIC_PATHS.robotGenerating;
        }
    }

    function renderProblemSolvingUI(questionsData, examTitle) {
        console.log("exam_spa_logic.js: renderProblemSolvingUI 호출됨");
        if (solveExamUITemplateHTML && questionsData && dynamicContentArea && robotImage) {
            dynamicContentArea.innerHTML = solveExamUITemplateHTML;
            dynamicContentArea.querySelector('#exam-title-placeholder-spa').textContent = `${escapeHtml(examTitle)} - 문제 풀이`;
            const questionsContainer = dynamicContentArea.querySelector('#questions-container-spa');
            questionsContainer.innerHTML = ''; // 이전 내용 비우기

            questionsData.forEach(q => {
                let questionHtml = `
                    <div class="card mb-3 q-item" data-question-id="${q.id}">
                        <div class="card-header"><strong>문제 ${q.question_number}.</strong></div>
                        <div class="card-body">
                            <p class="card-text">${q.question_text.replace(/\n/g, '<br>')}</p>`;
                if (q.question_type === "multiple_choice" && q.options && q.options.length > 0) {
                    q.options.forEach((opt, index) => {
                        const optionValue = escapeHtml(opt);
                        const optionId = `q${q.id}_opt${index}`;
                        questionHtml += `
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="answer_q_${q.id}" id="${optionId}" value="${optionValue}">
                                <label class="form-check-label" for="${optionId}">${escapeHtml(opt)}</label>
                            </div>`;
                    });
                } else if (q.question_type === "short_answer") {
                    questionHtml += `<input type="text" name="answer_q_${q.id}" class="form-control" placeholder="답을 입력하세요">`;
                }
                questionHtml += `</div></div>`;
                questionsContainer.innerHTML += questionHtml;
            });
            robotImage.src = STATIC_PATHS.robotSolving;

            const solveExamForm = document.getElementById('solveExamFormSpa');
            if (solveExamForm) {
                solveExamForm.addEventListener('submit', handleAnswerSubmission);
            }
        } else {
            console.error("exam_spa_logic.js: 문제 풀이 UI 템플릿, 문제 데이터, 또는 필수 DOM 요소를 찾을 수 없습니다.");
            showErrorState("문제 풀이 화면을 구성할 수 없습니다.");
        }
    }
    
    function renderResultsUI(resultsData) {
        console.log("exam_spa_logic.js: renderResultsUI 호출됨");
        if (resultUITemplateHTML && resultsData && dynamicContentArea && robotImage) {
            dynamicContentArea.innerHTML = resultUITemplateHTML;
            
            dynamicContentArea.querySelector('#result-exam-title-placeholder-spa').textContent = `시험 결과: ${escapeHtml(resultsData.exam_title)}`;
            dynamicContentArea.querySelector('.total-questions-count').textContent = resultsData.total_questions;
            dynamicContentArea.querySelector('.correct-answers-count').textContent = resultsData.correct_answers_count;
            dynamicContentArea.querySelector('.exam-score').textContent = Math.round(resultsData.score);
            dynamicContentArea.querySelector('.flo-comment-text').textContent = escapeHtml(resultsData.flo_comment);

            dynamicContentArea.querySelector('.download-questions-btn').href = APP_URLS.downloadQuestionsTemplate.replace('0', resultsData.exam_id);
            dynamicContentArea.querySelector('.download-answers-btn').href = APP_URLS.downloadAnswersTemplate.replace('0', resultsData.exam_id);
            
            const qResultsContainer = dynamicContentArea.querySelector('#question-results-container-spa');
            qResultsContainer.innerHTML = '';
            if (resultsData.user_answers_details) {
                resultsData.user_answers_details.forEach(ua => {
                    const cardClass = ua.is_correct ? 'border-success' : 'border-danger';
                    const headerClass = ua.is_correct ? 'bg-success-subtle text-success-emphasis' : 'bg-danger-subtle text-danger-emphasis';
                    const resultText = ua.is_correct ? '(정답)' : '(오답)';
                    let detailHtml = `
                        <div class="card mb-3 ${cardClass}">
                            <div class="card-header ${headerClass}">
                               <strong>문제 ${ua.question_number}.</strong> ${resultText}
                            </div>
                            <div class="card-body">
                                <p class="card-text"><strong>문제:</strong> ${ua.question_text.replace(/\n/g, '<br>')}</p>
                                <p><strong>제출한 답:</strong> ${escapeHtml(ua.submitted_answer) || "답변 안 함"}</p>
                                <p><strong>정답:</strong> ${escapeHtml(ua.correct_answer)}</p>`;
                    if (ua.explanation) {
                        detailHtml += `<p><strong>해설:</strong> ${ua.explanation.replace(/\n/g, '<br>')}</p>`;
                    }
                    detailHtml += `</div></div>`;
                    qResultsContainer.innerHTML += detailHtml;
                });
            }
            robotImage.src = STATIC_PATHS.robotResults;
        } else {
            console.error("exam_spa_logic.js: 결과 UI 템플릿, 결과 데이터, 또는 필수 DOM 요소를 찾을 수 없습니다.");
            showErrorState("결과를 표시할 수 없습니다.");
        }
    }

    function showErrorState(message) {
        console.error("exam_spa_logic.js: showErrorState 호출됨 - 메시지:", message);
        if (dynamicContentArea) {
            const uploadPageUrl = (typeof APP_URLS !== 'undefined' && APP_URLS.uploadPageUrl) ? APP_URLS.uploadPageUrl : '/'; // 기본 URL
            dynamicContentArea.innerHTML = `
                <div class="alert alert-danger text-center" role="alert">
                    ${escapeHtml(message)}
                    <br>
                    <a href="${uploadPageUrl}" class="alert-link mt-3 d-block">PDF 업로드 페이지로 돌아가기</a>
                </div>`;
        }
        if (robotImage && typeof STATIC_PATHS !== 'undefined' && STATIC_PATHS.robotIdle) {
            robotImage.src = STATIC_PATHS.robotIdle;
        }
    }
    
    function escapeHtml(unsafe) {
    if (unsafe === null || typeof unsafe === 'undefined') {
        return '';
    }
    // 먼저 toString()으로 문자열로 변환
    let safeString = unsafe.toString();

    safeString = safeString.replace(/&/g, "&");
    safeString = safeString.replace(/</g, "<");
    safeString = safeString.replace(/>/g, ">");
    safeString = safeString.replace(/"/g, '"'); // 큰따옴표는 "
    safeString = safeString.replace(/'/g, "'"); // 작은따옴표는 ' (또는 ')

    return safeString;
    }

    // --- AJAX 호출 함수들 ---
    function startProblemGeneration() {
        console.log("exam_spa_logic.js: startProblemGeneration 함수 호출 시작");
        showInitialLoading(); // 페이지 로드 시 먼저 로딩 UI 표시

        const ajaxUrl = APP_URLS.processPdf; // views.py에서 전달된 exam_document_id 포함 URL
        console.log("exam_spa_logic.js: 문제 생성 요청 URL:", ajaxUrl);

        fetch(ajaxUrl, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfTokenValue()
            },
            // body: FormData는 이 경우 필요 없음 (ID가 URL에 이미 있으므로)
        })
        .then(response => {
            console.log("exam_spa_logic.js: 문제 생성 응답 상태:", response.status);
            if (!response.ok) { 
                return response.json().then(errData => { // 에러 응답도 JSON으로 파싱 시도
                    console.error("exam_spa_logic.js: 문제 생성 서버 에러 응답:", errData);
                    throw errData; // 파싱된 에러 객체를 throw
                }).catch(parsingError => { // JSON 파싱 실패 시
                    console.error("exam_spa_logic.js: 문제 생성 서버 에러 응답 파싱 실패:", parsingError);
                    throw new Error(`서버 에러: ${response.status} ${response.statusText}`); // 일반 에러 객체 throw
                });
            }
            return response.json();
        })
        .then(data => {
            console.log("exam_spa_logic.js: 문제 생성 AJAX 응답 데이터:", data);
            if (data.status === 'completed' && data.exam_id && data.questions) {
                currentGeneratedExamId = data.exam_id;
                renderProblemSolvingUI(data.questions, data.exam_document_title);
            } else {
                showErrorState(data.message || '문제 생성에 실패했습니다 (데이터 형식 오류).');
            }
        })
        .catch(error => {
            console.error('exam_spa_logic.js: 문제 생성 AJAX 요청/처리 중 오류:', error);
            let errorMessage = '문제 생성 중 알 수 없는 오류가 발생했습니다.';
            if (error && error.message) { // 서버에서 보낸 JSON 에러 메시지 또는 일반 Error 객체의 메시지
                errorMessage = error.message;
            } else if (typeof error === 'string') {
                errorMessage = error;
            }
            showErrorState(errorMessage);
        });
    }

    function handleAnswerSubmission(event) {
        event.preventDefault();
        console.log("exam_spa_logic.js: handleAnswerSubmission 호출됨");
        showGenericLoading("채점 중...", "robotScoring");

        const formData = new FormData(event.target); // event.target은 제출된 form 요소
        const scoringUrl = APP_URLS.processScoringTemplate.replace('0', currentGeneratedExamId);
        console.log("exam_spa_logic.js: 답안 제출 요청 URL:", scoringUrl);

        fetch(scoringUrl, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfTokenValue()
            }
        })
        .then(response => {
            console.log("exam_spa_logic.js: 채점 응답 상태:", response.status);
            if (!response.ok) { 
                return response.json().then(errData => { throw errData; })
                                 .catch(() => { throw new Error(`서버 에러: ${response.status} ${response.statusText}`); });
            }
            return response.json();
        })
        .then(data => {
            console.log("exam_spa_logic.js: 채점 AJAX 응답 데이터:", data);
            if (data.status === 'completed' && data.session_id && data.results) {
                renderResultsUI(data.results);
            } else {
                showErrorState(data.message || '채점에 실패했습니다.');
            }
        })
        .catch(error => {
            console.error('exam_spa_logic.js: 채점 AJAX 요청/처리 중 오류:', error);
            let errorMessage = '채점 중 알 수 없는 오류가 발생했습니다.';
            if (error && error.message) errorMessage = error.message;
            else if (typeof error === 'string') errorMessage = error;
            showErrorState(errorMessage);
        });
    }

    function getCsrfTokenValue() {
        // exam_spa_page.html에 <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}"> 가 있어야 함
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput) {
            return csrfInput.value;
        }
        console.warn("CSRF 토큰 input을 찾을 수 없습니다. POST 요청이 실패할 수 있습니다.");
        return ''; // 또는 에러 발생
    }

    // --- 페이지 로드 시 초기 작업 ---
    if (typeof EXAM_DOCUMENT_ID !== 'undefined' && EXAM_DOCUMENT_ID && 
        typeof APP_URLS !== 'undefined' && APP_URLS.processPdf) {
        console.log("exam_spa_logic.js: 초기화 시작, EXAM_DOCUMENT_ID:", EXAM_DOCUMENT_ID);
        startProblemGeneration();
    } else {
        console.error("exam_spa_logic.js: 초기화에 필요한 EXAM_DOCUMENT_ID 또는 APP_URLS.processPdf가 정의되지 않았습니다.");
        showErrorState("페이지 초기화에 실패했습니다. PDF 업로드 페이지로 돌아가세요.");
    }
});