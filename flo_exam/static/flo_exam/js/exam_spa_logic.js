// FLO/flo_exam/static/flo_exam/js/exam_spa_logic.js
document.addEventListener('DOMContentLoaded', function() {
    console.log("exam_spa_logic.js: DOM Content Loaded");

    // HTML에서 전달된 전역 변수 존재 여부 확인
    if (typeof EXAM_DOCUMENT_ID === 'undefined' ||
        typeof EXAM_DOCUMENT_TITLE === 'undefined' ||
        typeof PAGE_INITIAL_MESSAGE === 'undefined' ||
        typeof APP_URLS === 'undefined' ||
        typeof STATIC_PATHS === 'undefined') {
        console.error("exam_spa_logic.js: 필수 전역 변수가 HTML에서 전달되지 않았습니다.");
        const errorFallbackArea = document.getElementById('dynamic-content-area') || document.body;
        errorFallbackArea.innerHTML = `<div class="alert alert-danger text-center m-5" role="alert">페이지 초기화 오류. <a href="/" class="alert-link">처음으로</a></div>`;
        return; // 실행 중단
    }
    console.log("exam_spa_logic.js: 전역 변수 확인 완료 - EXAM_DOCUMENT_ID:", EXAM_DOCUMENT_ID);

    const dynamicContentArea = document.getElementById('dynamic-content-area');
    const robotImageElement = document.getElementById('robot-image'); // 변수명 변경

    // HTML <template> 태그에서 UI 조각 가져오기
    const loadingUITemplateHTML = document.getElementById('loading-ui-template-spa')?.innerHTML;
    const solveExamUITemplateHTML = document.getElementById('solve-exam-ui-template-spa')?.innerHTML;
    const resultUITemplateHTML = document.getElementById('exam-result-ui-template-spa')?.innerHTML;

    let currentGeneratedExamId = null; // 생성된 시험의 ID (채점 및 PDF 다운로드 시 사용)
    // let currentQuestionsDataForSolving = []; // 현재 풀고 있는 문제 데이터 (필요시 사용)

    // --- UI 렌더링 함수들 ---
    function showInitialLoading() {
        console.log("exam_spa_logic.js: showInitialLoading 호출됨");
        if (loadingUITemplateHTML && dynamicContentArea && robotImageElement) {
            dynamicContentArea.innerHTML = loadingUITemplateHTML;
            dynamicContentArea.querySelector('.loading-text').textContent = PAGE_INITIAL_MESSAGE;
            robotImageElement.src = STATIC_PATHS.robotGenerating;
        } else {
            console.error("exam_spa_logic.js: 로딩 UI 템플릿 또는 DOM 요소를 찾을 수 없습니다. (showInitialLoading)");
            if (dynamicContentArea) dynamicContentArea.innerHTML = `<p class="text-center py-5">${PAGE_INITIAL_MESSAGE}<br><span class="spinner-border text-primary mt-2"></span></p>`;
            if (robotImageElement) robotImageElement.src = STATIC_PATHS.robotGenerating;
        }
    }
    
    function showGenericLoading(message, robotStateKey = "robotGenerating") {
        console.log(`exam_spa_logic.js: showGenericLoading 호출됨 - 메시지: ${message}, 로봇: ${robotStateKey}`);
        if (loadingUITemplateHTML && dynamicContentArea && robotImageElement) {
            dynamicContentArea.innerHTML = loadingUITemplateHTML;
            dynamicContentArea.querySelector('.loading-text').textContent = message;
            robotImageElement.src = STATIC_PATHS[robotStateKey] || STATIC_PATHS.robotGenerating;
        } else {
            console.error("exam_spa_logic.js: 로딩 UI 템플릿 또는 DOM 요소를 찾을 수 없습니다. (showGenericLoading)");
            if (dynamicContentArea) dynamicContentArea.innerHTML = `<p class="text-center py-5">${message}<br><span class="spinner-border text-primary mt-2"></span></p>`;
            if (robotImageElement) robotImageElement.src = STATIC_PATHS[robotStateKey] || STATIC_PATHS.robotGenerating;
        }
    }

    function renderProblemSolvingUI(questionsData, examTitle) {
        console.log("exam_spa_logic.js: renderProblemSolvingUI 호출됨. 받은 questionsData:", questionsData);
        // currentQuestionsDataForSolving = questionsData; // 필요시 저장

        if (solveExamUITemplateHTML && questionsData && Array.isArray(questionsData) && dynamicContentArea && robotImageElement) {
            dynamicContentArea.innerHTML = solveExamUITemplateHTML;
            dynamicContentArea.querySelector('#exam-title-placeholder-spa').textContent = `${escapeHtml(examTitle)} - 문제 풀이`;
            const questionsContainer = dynamicContentArea.querySelector('#questions-container-spa');
            questionsContainer.innerHTML = ''; 

            questionsData.forEach(q => {
                // console.log(`JS 처리 중인 문제 (ID: ${q.id}, 번호: ${q.question_number}, 타입: ${q.question_type}, 옵션:`, q.options, `)`);
                
                let questionHtml = `
                    <div class="card mb-3 q-item" data-question-id="${q.id}">
                        <div class="card-header"><strong>문제 ${q.question_number}.</strong></div>
                        <div class="card-body">
                            <p class="card-text">${q.question_text ? q.question_text.replace(/\n/g, '<br>') : '문제 내용 없음'}</p>`;
                
                const isMultipleChoice = q.question_type === "multiple_choice";
                const hasOptions = q.options && Array.isArray(q.options) && q.options.length > 0;
                
                if (isMultipleChoice && hasOptions) {
                    q.options.forEach((opt, index) => {
                        const optionTextForDisplay = (opt === null || typeof opt === 'undefined' || String(opt).trim() === "") ? "(선택지 내용 없음)" : escapeHtml(opt);
                        const optionValueForInput = (opt === null || typeof opt === 'undefined') ? "" : escapeHtml(opt); // 값은 원본 또는 빈 문자열
                        const optionId = `q${q.id}_opt${index}`;
                        questionHtml += `
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="answer_q_${q.id}" id="${optionId}" value="${optionValueForInput}">
                                <label class="form-check-label" for="${optionId}">${optionTextForDisplay}</label>
                            </div>`;
                    });
                } else if (q.question_type === "short_answer") {
                    questionHtml += `<input type="text" name="answer_q_${q.id}" class="form-control" placeholder="답을 입력하세요">`;
                } else {
                    if (isMultipleChoice) { // 객관식인데 옵션이 없는 경우
                         questionHtml += `<p class="text-muted"><em>이 문제의 선택지를 불러올 수 없습니다.</em></p>`;
                    }
                    console.warn(`문제 ${q.question_number}: 선택지 없음 또는 question_type(${q.question_type})이 올바르지 않음. options:`, q.options);
                }
                questionHtml += `</div></div>`;
                questionsContainer.innerHTML += questionHtml;
            });
            robotImageElement.src = STATIC_PATHS.robotSolving;

            const solveExamForm = document.getElementById('solveExamFormSpa');
            if (solveExamForm) {
                solveExamForm.addEventListener('submit', handleAnswerSubmission);
            }
        } else {
            console.error("exam_spa_logic.js: 문제 풀이 UI 구성 실패. 템플릿, 데이터, DOM 요소 확인 필요.");
            showErrorState("문제 풀이 화면을 구성할 수 없습니다. 데이터를 확인해주세요.");
        }
    }
    
    function renderResultsUI(resultsData) {
        console.log("exam_spa_logic.js: renderResultsUI 호출됨. 받은 resultsData:", resultsData);
        if (resultUITemplateHTML && resultsData && dynamicContentArea && robotImageElement) {
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
            if (resultsData.user_answers_details && Array.isArray(resultsData.user_answers_details)) {
                resultsData.user_answers_details.forEach(ua => {
                    const cardClass = ua.is_correct ? 'border-success' : 'border-danger';
                    const headerBgClass = ua.is_correct ? 'bg-success-subtle text-success-emphasis' : 'bg-danger-subtle text-danger-emphasis';
                    const resultText = ua.is_correct ? '<span class="badge bg-success">정답</span>' : '<span class="badge bg-danger">오답</span>';
                    
                    let detailHtml = `
                        <div class="card mb-3 ${cardClass}">
                            <div class="card-header ${headerBgClass}">
                               <strong class="me-2">문제 ${ua.question_number}.</strong> ${resultText}
                            </div>
                            <div class="card-body">
                                <p class="card-text mb-2"><strong>문제:</strong> ${ua.question_text ? ua.question_text.replace(/\n/g, '<br>') : '문제 내용 없음'}</p>`;
                    
                    if (ua.options && ua.options.length > 0) {
                        detailHtml += '<p class="mb-1"><strong>선택지:</strong></p><ul class="list-unstyled ps-3">';
                        ua.options.forEach(opt => {
                            let li_class = "";
                            let icon = "";
                            const escOpt = escapeHtml(opt);
                            const escCorrectAns = escapeHtml(ua.correct_answer);
                            const escSubmittedAns = escapeHtml(ua.submitted_answer);

                            if (escOpt === escCorrectAns) {
                                li_class = "text-success fw-bold";
                                icon = '<i class="bi bi-check-circle-fill me-1"></i>';
                            }
                            if (escOpt === escSubmittedAns && !ua.is_correct) {
                                li_class = "text-danger"; // 사용자가 선택한 오답
                                icon = '<i class="bi bi-x-circle-fill me-1"></i>';
                            } else if (escOpt === escSubmittedAns && ua.is_correct) { // 사용자가 선택한 정답
                                icon = '<i class="bi bi-check-circle-fill me-1 text-success"></i>';
                            }
                            detailHtml += `<li class="${li_class}">${icon}${escOpt}</li>`;
                        });
                        detailHtml += '</ul>';
                    }
                    
                    detailHtml += `<p class="mt-2 mb-1"><strong>제출한 답:</strong> ${escapeHtml(ua.submitted_answer) || "답변 안 함"}</p>`;
                    if (ua.question_type !== "multiple_choice" || (ua.options && ua.options.length === 0) || (ua.options && !ua.options.map(o => escapeHtml(o)).includes(escapeHtml(ua.correct_answer)))) {
                        detailHtml += `<p class="mb-1"><strong>정답:</strong> ${escapeHtml(ua.correct_answer)}</p>`;
                    }

                    if (ua.explanation) {
                        detailHtml += `<p class="mt-2 mb-0"><strong>해설:</strong> ${ua.explanation.replace(/\n/g, '<br>')}</p>`;
                    }
                    detailHtml += `</div></div>`;
                    qResultsContainer.innerHTML += detailHtml;
                });
            }
            robotImageElement.src = STATIC_PATHS.robotResults;
        } else {
            console.error("exam_spa_logic.js: 결과 UI 구성 실패. 템플릿, 데이터, DOM 요소 확인 필요.");
            showErrorState("결과를 표시할 수 없습니다.");
        }
    }

    function showErrorState(message) {
        console.error("exam_spa_logic.js: showErrorState 호출됨 - 메시지:", message);
        if (dynamicContentArea && robotImageElement) {
            const uploadPageUrl = (typeof APP_URLS !== 'undefined' && APP_URLS.uploadPageUrl) ? APP_URLS.uploadPageUrl : '/';
            dynamicContentArea.innerHTML = `
                <div class="alert alert-danger text-center m-3" role="alert">
                    <h4>오류 발생</h4>
                    <p>${escapeHtml(message)}</p>
                    <hr>
                    <a href="${uploadPageUrl}" class="btn btn-primary mt-2">PDF 업로드 페이지로 돌아가기</a>
                </div>`;
            robotImageElement.src = STATIC_PATHS.robotIdle;
        } else {
            alert("치명적 오류: 에러 메시지를 표시할 영역을 찾을 수 없습니다. " + message);
        }
    }
    
    function escapeHtml(unsafe) {
        if (unsafe === null || typeof unsafe === 'undefined') return '';
        let safeString = unsafe.toString();
        safeString = safeString.replace(/&/g, "&amp;");   // '&'를 '&amp;'로
        safeString = safeString.replace(/</g, "&lt;");    // '<'를 '&lt;'로
        safeString = safeString.replace(/>/g, "&gt;");    // '>'를 '&gt;'로
        safeString = safeString.replace(/"/g, "&quot;");  // '"'를 '&quot;'로
        safeString = safeString.replace(/'/g, "&#039;");  // '''를 '&#039;' 또는 '&apos;'로 (&#039;이 더 범용적)
        return safeString;
    }

    // --- AJAX 호출 함수들 ---
    function startProblemGeneration() {
        console.log("exam_spa_logic.js: startProblemGeneration 함수 호출 시작");
        showInitialLoading(); 

        const ajaxUrl = APP_URLS.processPdf;
        console.log("exam_spa_logic.js: 문제 생성 요청 URL:", ajaxUrl);

        fetch(ajaxUrl, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfTokenValue()
            },
        })
        .then(response => {
            console.log("exam_spa_logic.js: 문제 생성 응답 상태:", response.status);
            if (!response.ok) { 
                return response.json().then(errData => { throw errData; })
                                 .catch(() => { throw new Error(`서버 응답 오류: ${response.status} ${response.statusText}`); });
            }
            return response.json();
        })
        .then(data => {
            console.log("exam_spa_logic.js: 문제 생성 AJAX 응답 데이터:", data);
            if (data.status === 'completed' && data.exam_id && data.questions) {
                currentGeneratedExamId = data.exam_id; // 생성된 시험 ID 저장
                renderProblemSolvingUI(data.questions, data.exam_document_title);
            } else {
                showErrorState(data.message || '문제 생성에 실패했습니다 (서버 데이터 오류).');
            }
        })
        .catch(error => {
            console.error('exam_spa_logic.js: 문제 생성 AJAX 요청/처리 중 최종 오류:', error);
            let errorMessage = '문제 생성 중 통신 또는 처리 오류가 발생했습니다.';
            if (error && error.message) errorMessage = error.message;
            else if (typeof error === 'string') errorMessage = error;
            showErrorState(errorMessage);
        });
    }

    function handleAnswerSubmission(event) {
        event.preventDefault();
        console.log("exam_spa_logic.js: handleAnswerSubmission 호출됨");
        showGenericLoading("채점 중입니다. 잠시만 기다려 주세요...", "robotScoring");

        const formData = new FormData(event.target);
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
                                 .catch(() => { throw new Error(`서버 응답 오류: ${response.status} ${response.statusText}`); });
            }
            return response.json();
        })
        .then(data => {
            console.log("exam_spa_logic.js: 채점 AJAX 응답 데이터:", data);
            if (data.status === 'completed' && data.session_id && data.results) {
                renderResultsUI(data.results);
            } else {
                showErrorState(data.message || '채점에 실패했습니다 (서버 데이터 오류).');
            }
        })
        .catch(error => {
            console.error('exam_spa_logic.js: 채점 AJAX 요청/처리 중 최종 오류:', error);
            let errorMessage = '채점 중 통신 또는 처리 오류가 발생했습니다.';
            if (error && error.message) errorMessage = error.message;
            else if (typeof error === 'string') errorMessage = error;
            showErrorState(errorMessage);
        });
    }

    function getCsrfTokenValue() {
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput) {
            return csrfInput.value;
        }
        const csrfCookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        if (csrfCookie) {
            return csrfCookie.split('=')[1];
        }
        console.warn("CSRF 토큰을 찾을 수 없습니다. POST 요청이 실패할 수 있습니다.");
        return '';
    }

    // --- 페이지 로드 시 초기 작업 ---
    if (typeof EXAM_DOCUMENT_ID !== 'undefined' && EXAM_DOCUMENT_ID && 
        typeof APP_URLS !== 'undefined' && APP_URLS.processPdf &&
        typeof STATIC_PATHS !== 'undefined' && typeof PAGE_INITIAL_MESSAGE !== 'undefined') {
        console.log("exam_spa_logic.js: 초기화 시작, EXAM_DOCUMENT_ID:", EXAM_DOCUMENT_ID);
        startProblemGeneration(); // 페이지 로드 시 바로 문제 생성 요청 시작
    } else {
        console.error("exam_spa_logic.js: 초기화에 필요한 전역 변수(EXAM_DOCUMENT_ID, APP_URLS.processPdf 등)가 정의되지 않았습니다.");
        showErrorState("페이지를 초기화하는 데 필요한 정보가 부족합니다. 이전 페이지로 돌아가서 다시 시도해주세요.");
    }
});