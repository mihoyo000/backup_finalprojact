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
        const thinkingMessageElement = appendMessage('...', 'bot', true);

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

            // '생각 중...' 메시지 제거
            thinkingMessageElement.remove();

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.answer || '서버 응답 오류');
            }

            const data = await response.json();
            // 봇의 응답을 화면에 표시
            appendMessage(data.answer, 'bot');

        } catch (error) {
            console.error('Chatbot error:', error);
            appendMessage('죄송합니다. 오류가 발생했어요. 다시 시도해주세요.', 'bot');
        }
    });

    /**
     * 메시지를 챗봇 보드에 추가하는 함수
     * @param {string} message - 표시할 메시지 텍스트
     * @param {string} type - 'me'(사용자) 또는 'bot'(챗봇)
     * @param {boolean} isThinking - '생각 중' 상태인지 여부
     * @returns {HTMLElement} - 생성된 메시지 컨테이너 엘리먼트
     */
    function appendMessage(message, type, isThinking = false) {
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
        if (isThinking) {
            bubbleDiv.classList.add('thinking');
        }
        
        const span = document.createElement('span');
        span.innerHTML = message.replace(/\n/g, '<br>'); // 줄바꿈 문자를 <br>로 변환
        
        bubbleDiv.appendChild(span);
        contextDiv.appendChild(bubbleDiv);
        
        messageContainer.appendChild(personDiv);
        messageContainer.appendChild(contextDiv);
        
        chatbotBoard.appendChild(messageContainer);

        // 새 메시지가 추가되면 스크롤을 맨 아래로 이동
        chatbotBoard.scrollTop = chatbotBoard.scrollHeight;
        
        return messageContainer;
    }

    // 4. 테마 변경 감지 및 적용
    // 이 부분은 프로젝트의 실제 테마 변경 로직과 연동해야 합니다.
    // 여기서는 예시로 `html` 태그의 `data-bs-theme` 속성을 감지합니다.
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
            attributes: true // 속성 변경 감지
        });

        // 초기 테마 설정
        const initialTheme = htmlElement.getAttribute('data-bs-theme') || 'light';
        chatbotThemeWrapper.setAttribute('data-theme', initialTheme);
    };

    observeThemeChanges();
});