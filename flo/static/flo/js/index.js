// static/flo/js/index.js
document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM fully loaded and parsed");

    const fullpageElement = document.getElementById('fullpage');
    const scrollToTopBtn = document.getElementById('scroll-to-top');

    if (fullpageElement) {
        console.log("Fullpage element found. Initializing fullPage.js...");
        try {
            new fullpage('#fullpage', {
                licenseKey: 'YOUR_KEY_HERE', // 실제 라이선스 키로 교체하세요.

                // Navigation
                anchors:['program-start', 'features', 'community-posts'], // 수정된 앵커
                navigation: true,
                navigationPosition: 'right',
                navigationTooltips: ['프로그램 시작하기', '기능 소개', '커뮤니티 - 인기글'], // 수정된 툴팁
                showActiveTooltip: false, // CSS에서 항상 보이도록 제어하므로 false 유지 또는 true로 변경 후 CSS 조정

                // Scrolling
                scrollingSpeed: 700,
                autoScrolling: true,
                fitToSection: true,
                fitToSectionDelay: 1000,
                scrollBar: false,
                easing: 'easeInOutCubic',
                loopBottom: false,
                loopTop: false,
                keyboardScrolling: true,
                animateAnchor: true,
                recordHistory: true,

                // Design
                verticalCentered: false, // 컨텐츠를 섹션 내에서 직접 정렬할 것이므로 false
<<<<<<< HEAD
                fixedElements: '#header, .site-footer',
=======
                fixedElements: '#header',
>>>>>>> b0590081b1e26a670b5c09461d4acb164dcc58f5
                responsiveWidth: 0,
                lazyLoading: true,

                // Callbacks
                onLeave: function(origin, destination, direction){
                    console.log("Leaving section " + origin.index + " | Destination: " + destination.index);
                    if (scrollToTopBtn) {
                        if (destination.index > 0) {
                            scrollToTopBtn.style.display = "block";
                            setTimeout(() => scrollToTopBtn.style.opacity = '1', 10);
                        } else {
                            scrollToTopBtn.style.opacity = '0';
                            setTimeout(() => {
                                if (scrollToTopBtn.style.opacity === '0') {
                                    scrollToTopBtn.style.display = "none";
                                }
                            }, 300);
                        }
                    }
                },
                afterLoad: function(origin, destination, direction){
                    console.log("Loaded section " + destination.index);
                    if (scrollToTopBtn && destination.index === 0) {
                        scrollToTopBtn.style.opacity = '0';
                        scrollToTopBtn.style.display = "none";
                    } else if (scrollToTopBtn && destination.index > 0) {
                        scrollToTopBtn.style.display = "block";
                        scrollToTopBtn.style.opacity = '1';
                    }
                },
                afterRender: function(){
                    console.log("fullPage.js rendered!");
                    // 툴팁이 CSS에 의해 항상 보이도록 설정되어 있으므로, JS에서 추가 조작 불필요
                    if (scrollToTopBtn && typeof fullpage_api !== 'undefined' && fullpage_api.getActiveSection && fullpage_api.getActiveSection().index === 0) {
                        scrollToTopBtn.style.display = "none";
                        scrollToTopBtn.style.opacity = '0';
                    } else if (scrollToTopBtn && typeof fullpage_api !== 'undefined') { // fullpage_api 존재 확인
                        scrollToTopBtn.style.display = "block";
                        scrollToTopBtn.style.opacity = '1';
                    }

                    // 변경/추가: 툴팁 클릭 가능하게 만들기
                    const tooltips = document.querySelectorAll('#fp-nav .fp-tooltip');
                    tooltips.forEach(tooltip => {
                        // 툴팁 클릭 시 내비게이션 실행
                        tooltip.addEventListener('click', function() {
                            // 클릭된 툴팁의 부모 <li> 요소를 찾음
                            const parentLi = this.closest('li');
                            if (parentLi) {
                                // <li> 요소 안의 <a> 태그(실제 내비게이션 링크)를 찾음
                                const anchor = parentLi.querySelector('a');
                                if (anchor) {
                                    anchor.click(); // 해당 <a> 태그의 클릭 이벤트를 강제로 발생시킴
                                }
                            }
                        });
                    });
                    console.log("Tooltips clickability and hover behavior enhanced.");
                }
            });
            console.log("fullPage.js initialized successfully.");
        } catch (error) {
            console.error("Error initializing fullPage.js:", error);
        }

        if (scrollToTopBtn) {
            scrollToTopBtn.addEventListener('click', function() {
                if (typeof fullpage_api !== 'undefined') {
                    fullpage_api.moveTo(1);
                }
            });
        }

    } else {
        console.warn("Fullpage element not found. Skipping fullPage.js initialization.");
    }
});