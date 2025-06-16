// flo_exam/static/flo_exam/js/chatbot.js

document.addEventListener('DOMContentLoaded', () => {

    // 1. DOM 요소 가져오기
    const chatbotToggleButton = document.getElementById('chatbot-toggle-button');
    const chatbotWindow = document.getElementById('chatbot-window');
    const chatbotCloseButton = document.getElementById('chatbot-close-button');
    const chatbotForm = document.getElementById('chatbot-form');
    const chatbotInput = document.getElementById('chatbot-input');
    const chatbotBoard = document.getElementById('chatbot-board');
    const chatbotThemeWrapper = document.getElementById('chatbot-wrapper');

    // ★★★ 로딩 애니메이션을 제어하기 위한 전역 변수 추가 ★★★
    let loadingInterval = null;

    // 요소가 없으면 스크립트 실행 중단
    if (!chatbotToggleButton || !chatbotWindow || !chatbotCloseButton || !chatbotForm) {
        return;
    }

    // 2. 챗봇 창 열고 닫기 이벤트 리스너
    const toggleChatbot = () => {
        chatbotWindow.classList.toggle('is-hidden');
    };
    chatbotToggleButton.addEventListener('click', toggleChatbot);
    chatbotCloseButton.addEventListener('click', toggleChatbot);

    // 3. 챗봇 메시지 전송 이벤트 리스너
    chatbotForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userMessage = chatbotInput.value.trim();

        if (!userMessage) return;

        // 사용자 메시지를 화면에 표시
        appendMessage(userMessage, 'me');
        chatbotInput.value = ''; // 입력창 초기화

        // '생각 중...' 메시지 표시
        // ★★★ 수정: 'isThinking' 대신 초기 텍스트를 전달하고, 텍스트가 담긴 <span> 요소를 받아옴 ★★★
        const loadingSpanElement = appendMessage('답변을 생성 중입니다', 'bot');
        
        // ★★★ 추가: 로딩 애니메이션 시작 ★★★
        startLoadingAnimation(loadingSpanElement);

        try {
            // 서버로 메시지 전송
            const response = await fetch(CHATBOT_AJAX_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN,
                },
                body: JSON.stringify({ question: userMessage }),
            });
            
            // ★★★ 추가: 응답을 받으면 애니메이션 중지 ★★★
            stopLoadingAnimation();

            if (!response.ok) {
                const errorData = await response.json();
                // ★★★ 수정: '생각 중...' 메시지를 제거하는 대신 내용을 오류 메시지로 교체 ★★★
                loadingSpanElement.innerHTML = (errorData.answer || '서버 응답 오류').replace(/\n/g, '<br>');
                throw new Error(errorData.answer || '서버 응답 오류');
            }

            const data = await response.json();
            // ★★★ 수정: 봇의 응답으로 '생각 중...' 메시지의 내용을 교체 ★★★
            loadingSpanElement.innerHTML = data.answer.replace(/\n/g, '<br>');

        } catch (error) {
            console.error('Chatbot error:', error);
            // ★★★ 추가: 에러 발생 시에도 애니메이션을 멈춰야 함 ★★★
            stopLoadingAnimation();
            // ★★★ 수정: 오류 발생 시에도 '생각 중...' 메시지를 교체 (새 메시지 추가 대신) ★★★
            loadingSpanElement.innerHTML = '죄송합니다. 오류가 발생했어요. 다시 시도해주세요.';
        }
    });

    /**
     * 메시지를 챗봇 보드에 추가하는 함수
     * @param {string} message - 표시할 메시지 텍스트
     * @param {string} type - 'me'(사용자) 또는 'bot'(챗봇)
     * @returns {HTMLElement} - 생성된 메시지의 텍스트가 담긴 <span> 엘리먼트
     */
    function appendMessage(message, type) { // isThinking 파라미터 제거
        const messageContainer = document.createElement('div');
        messageContainer.className = 'chat__conversation-board__message-container';
        if (type === 'me') {
            messageContainer.classList.add('reversed');
        }

        const personDiv = document.createElement('div');
        personDiv.className = 'chat__conversation-board__message__person';
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'chat__conversation-board__message__person__avatar';
        
        const avatarImg = document.createElement('img');
        avatarImg.src = (type === 'me') ? STATIC_URL_USER_AVATAR : STATIC_URL_ROBOT_AVATAR;
        avatarImg.alt = (type === 'me') ? 'User' : 'Flo';
        
        avatarDiv.appendChild(avatarImg);
        personDiv.appendChild(avatarDiv);
        
        const contextDiv = document.createElement('div');
        contextDiv.className = 'chat__conversation-board__message__context';
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'chat__conversation-board__message__bubble';
        
        const span = document.createElement('span');
        span.innerHTML = message.replace(/\n/g, '<br>');
        
        bubbleDiv.appendChild(span);
        contextDiv.appendChild(bubbleDiv);
        
        messageContainer.appendChild(personDiv);
        messageContainer.appendChild(contextDiv);
        
        chatbotBoard.appendChild(messageContainer);

        chatbotBoard.scrollTop = chatbotBoard.scrollHeight;
        
        // ★★★ 수정: 메시지 컨테이너 대신 텍스트가 담긴 span 요소를 반환 ★★★
        return span;
    }

    // ★★★ 추가: 로딩 애니메이션을 시작하고 중지하는 함수들 ★★★
    /**
     * 로딩 애니메이션을 시작하는 함수
     * @param {HTMLElement} element - 애니메이션을 적용할 텍스트 <span> 요소
     */
    function startLoadingAnimation(element) {
        let dotCount = 1;
        const baseText = "답변을 생성 중입니다";
        
        stopLoadingAnimation(); // 혹시 모를 이전 인터벌 제거

        loadingInterval = setInterval(() => {
            let dots = '.'.repeat(dotCount);
            element.textContent = baseText + dots;
            dotCount = (dotCount % 3) + 1; // 1, 2, 3을 반복
        }, 400); // 0.4초마다 점 개수 변경
    }

    /**
     * 로딩 애니메이션을 중지하는 함수
     */
    function stopLoadingAnimation() {
        if (loadingInterval) {
            clearInterval(loadingInterval);
            loadingInterval = null;
        }
    }


    // 4. 테마 변경 감지 및 적용 (기존 코드 유지)
    const observeThemeChanges = () => {
        const htmlElement = document.documentElement;
        
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'data-bs-theme') {
                    const newTheme = htmlElement.getAttribute('data-bs-theme');
                    chatbotThemeWrapper.setAttribute('data-theme', newTheme);
                    console.log(`Chatbot theme changed to: ${newTheme}`);
                }
            });
        });

        observer.observe(htmlElement, {
            attributes: true
        });

        const initialTheme = htmlElement.getAttribute('data-bs-theme') || 'light';
        chatbotThemeWrapper.setAttribute('data-theme', initialTheme);
    };

    // ★★★★★★★★★★★ 드래그 이동 및 리사이즈 기능 (업그레이드 버전) ★★★★★★★★★★★

    const draggableHeader = document.querySelector('#chatbot-window .chat__header');
    
    // 1. 드래그로 창 이동시키는 기능
    const makeDraggable = (element, handle) => {
        let offsetX = 0, offsetY = 0;

        handle.addEventListener('mousedown', (e) => {
            // 입력창이나 버튼 클릭 시에는 드래그 방지
            if (e.target.closest('button, input, a')) return;
            
            e.preventDefault();
            
            const rect = element.getBoundingClientRect();
            offsetX = e.clientX - rect.left;
            offsetY = e.clientY - rect.top;

            document.addEventListener('mousemove', drag);
            document.addEventListener('mouseup', stopDrag);
        });

        function drag(e) {
            element.style.left = (e.clientX - offsetX) + 'px';
            element.style.top = (e.clientY - offsetY) + 'px';
            // right, bottom 속성은 드래그 중에는 방해가 되므로 제거
            element.style.right = 'auto';
            element.style.bottom = 'auto';
        }

        function stopDrag() {
            document.removeEventListener('mousemove', drag);
            document.removeEventListener('mouseup', stopDrag);
        }
    };

    // 2. 모든 방향에서 리사이즈하는 기능
    const makeResizable = (element) => {
        const resizers = element.querySelectorAll('.resizer');
        const minWidth = 320;
        const minHeight = 450;
        let originalWidth, originalHeight, originalX, originalY, originalMouseX, originalMouseY;

        resizers.forEach(resizer => {
            resizer.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation(); // 드래그 이벤트 전파 방지

                const rect = element.getBoundingClientRect();
                originalWidth = rect.width;
                originalHeight = rect.height;
                originalX = rect.left;
                originalY = rect.top;
                originalMouseX = e.pageX;
                originalMouseY = e.pageY;
                
                // right, bottom 속성은 리사이즈 중 방해가 될 수 있으므로 제거하고 left, top을 사용
                element.style.right = 'auto';
                element.style.bottom = 'auto';
                element.style.left = originalX + 'px';
                element.style.top = originalY + 'px';

                window.addEventListener('mousemove', resize);
                window.addEventListener('mouseup', stopResize);
            });

            function resize(e) {
                if (resizer.classList.contains('resizer-bottom-right')) {
                    const width = originalWidth + (e.pageX - originalMouseX);
                    const height = originalHeight + (e.pageY - originalMouseY);
                    if (width > minWidth) element.style.width = width + 'px';
                    if (height > minHeight) element.style.height = height + 'px';
                } else if (resizer.classList.contains('resizer-bottom-left')) {
                    const width = originalWidth - (e.pageX - originalMouseX);
                    const height = originalHeight + (e.pageY - originalMouseY);
                    if (width > minWidth) {
                        element.style.width = width + 'px';
                        element.style.left = originalX + (e.pageX - originalMouseX) + 'px';
                    }
                    if (height > minHeight) element.style.height = height + 'px';
                } else if (resizer.classList.contains('resizer-top-right')) {
                    const width = originalWidth + (e.pageX - originalMouseX);
                    const height = originalHeight - (e.pageY - originalMouseY);
                    if (width > minWidth) element.style.width = width + 'px';
                    if (height > minHeight) {
                        element.style.height = height + 'px';
                        element.style.top = originalY + (e.pageY - originalMouseY) + 'px';
                    }
                } else if (resizer.classList.contains('resizer-top-left')) {
                    const width = originalWidth - (e.pageX - originalMouseX);
                    const height = originalHeight - (e.pageY - originalMouseY);
                    if (width > minWidth) {
                        element.style.width = width + 'px';
                        element.style.left = originalX + (e.pageX - originalMouseX) + 'px';
                    }
                    if (height > minHeight) {
                        element.style.height = height + 'px';
                        element.style.top = originalY + (e.pageY - originalMouseY) + 'px';
                    }
                } else if (resizer.classList.contains('resizer-right')) {
                    const width = originalWidth + (e.pageX - originalMouseX);
                    if (width > minWidth) element.style.width = width + 'px';
                } else if (resizer.classList.contains('resizer-left')) {
                    const width = originalWidth - (e.pageX - originalMouseX);
                    if (width > minWidth) {
                        element.style.width = width + 'px';
                        element.style.left = originalX + (e.pageX - originalMouseX) + 'px';
                    }
                } else if (resizer.classList.contains('resizer-bottom')) {
                    const height = originalHeight + (e.pageY - originalMouseY);
                    if (height > minHeight) element.style.height = height + 'px';
                } else { // Top
                    const height = originalHeight - (e.pageY - originalMouseY);
                    if (height > minHeight) {
                        element.style.height = height + 'px';
                        element.style.top = originalY + (e.pageY - originalMouseY) + 'px';
                    }
                }
            }

            function stopResize() {
                window.removeEventListener('mousemove', resize);
                window.removeEventListener('mouseup', stopResize);
            }
        });
    };

    // 챗봇 창에 기능 적용
    if (chatbotWindow && draggableHeader) {
        makeDraggable(chatbotWindow, draggableHeader);
        makeResizable(chatbotWindow);
    }

    // ★★★★★★★★★★★ 기능 추가 끝 ★★★★★★★★★★★

    observeThemeChanges();
});