// static/flo/js/base.js

document.addEventListener('DOMContentLoaded', function () {

    // --- 테마 전환 로직 시작 ---
    const themeDropdown = document.querySelector('.theme-dropdown');
    if (themeDropdown) {
        const body = document.body;
        const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)');

        const headerLogoImg = document.getElementById('header-logo');
        const footerLogoImg = document.getElementById('footer-logo'); // 푸터 로고 이미지 요소 추가
        const themeToggleImg = document.getElementById('theme-toggle-icon');
        const langToggleImg = document.getElementById('lang-toggle-icon');
        const themeItemIcons = {
            light: document.getElementById('theme-item-icon-light'),
            dark: document.getElementById('theme-item-icon-dark'),
            auto: document.getElementById('theme-item-icon-auto')
        };
        const themeMenuItems = document.querySelectorAll('.theme-dropdown-menu .dropdown-item.theme-item');

        const getCurrentThemeSetting = () => localStorage.getItem('theme') || 'light'; // 기본값을 'light'로 명시

        const applyTheme = (selectedThemeSetting) => {
            let actualTheme;
            if (selectedThemeSetting === 'auto') {
                actualTheme = prefersDarkScheme.matches ? 'dark' : 'light';
            } else {
                actualTheme = selectedThemeSetting;
            }

            body.classList.remove('theme-light', 'theme-dark');
            if (actualTheme === 'dark') {
                body.classList.add('theme-dark');
            } else {
                body.classList.add('theme-light'); // 'light' 테마일 때도 명시적으로 클래스 추가
            }

            localStorage.setItem('theme', selectedThemeSetting);
            updateIcons(actualTheme, selectedThemeSetting);
            updateActiveDropdownItem(selectedThemeSetting);
        };

        const updateIcons = (currentActualTheme, currentThemeSetting) => {
            const paths = window.iconImagePaths;
            if (!paths) {
                console.error("iconImagePaths is not defined in window object.");
                return;
            }

            const lightP = paths.light;
            const darkP = paths.dark || paths.light;

            // 1. 헤더 로고 변경
            if (headerLogoImg) {
                headerLogoImg.src = (currentActualTheme === 'dark' && darkP.logo) ? darkP.logo : lightP.logo;
            }

            // START: 푸터 로고 변경 로직 추가
            if (footerLogoImg) {
                // 헤더 로고와 동일한 로직으로 푸터 로고 이미지 경로 설정
                footerLogoImg.src = (currentActualTheme === 'dark' && darkP.logo) ? darkP.logo : lightP.logo;
            }
            // END: 푸터 로고 변경 로직 추가

            // 2. 헤더 테마 토글 버튼 아이콘 변경
            if (themeToggleImg) {
                if (currentThemeSetting === 'light') {
                    themeToggleImg.src = lightP.themeLight;
                } else if (currentThemeSetting === 'dark') {
                    themeToggleImg.src = (currentActualTheme === 'dark' && darkP.themeDark) ? darkP.themeDark : lightP.themeDark;
                } else { // 'auto'
                    themeToggleImg.src = (currentActualTheme === 'dark' && darkP.themeAuto) ? darkP.themeAuto : lightP.themeAuto;
                }
            }

            // 3. 헤더 언어 토글 버튼 아이콘 변경
            if (langToggleImg) {
                langToggleImg.src = (currentActualTheme === 'dark' && darkP.translate) ? darkP.translate : lightP.translate;
            }

            // 4. 테마 드롭다운 내부 아이콘들 변경
            if (themeItemIcons.light) {
                 // 페이지가 라이트 모드이고, "라이트" 테마가 선택된 경우 -> 드롭다운 "라이트" 아이템의 아이콘은 (다크모드용) "라이트" 아이콘
                if (currentActualTheme === 'light' && currentThemeSetting === 'light' && darkP.themeLight) {
                    themeItemIcons.light.src = darkP.themeLight;
                } else {
                    themeItemIcons.light.src = (currentActualTheme === 'dark' && darkP.themeLight) ? darkP.themeLight : lightP.themeLight;
                }
            }
            if (themeItemIcons.dark) {
                themeItemIcons.dark.src = (currentActualTheme === 'dark' && darkP.themeDark) ? darkP.themeDark : lightP.themeDark;
            }
            if (themeItemIcons.auto) {
                themeItemIcons.auto.src = (currentActualTheme === 'dark' && darkP.themeAuto) ? darkP.themeAuto : lightP.themeAuto;
            }
        };

        const updateActiveDropdownItem = (themeSetting) => {
            themeMenuItems.forEach(item => {
                item.classList.toggle('active', item.dataset.themeMode === themeSetting);
            });
        };

        themeMenuItems.forEach(item => {
            item.addEventListener('click', () => {
                const selectedTheme = item.dataset.themeMode;
                applyTheme(selectedTheme);
            });
        });

        const handleSystemThemeChange = () => {
            if (getCurrentThemeSetting() === 'auto') {
                applyTheme('auto');
            }
        };

        if (prefersDarkScheme.addEventListener) {
            prefersDarkScheme.addEventListener('change', handleSystemThemeChange);
        } else if (prefersDarkScheme.addListener) {
            prefersDarkScheme.addListener(handleSystemThemeChange);
        }

        applyTheme(getCurrentThemeSetting());
    }
    // --- 테마 전환 로직 끝 ---


    // --- TOP 버튼 로직 (기존 유지) ---
    const scrollToTopBtn = document.getElementById('scroll-to-top');
    if (scrollToTopBtn && typeof fullpage_api === 'undefined') {
        let isScrolling;
        window.onscroll = function() {
            window.clearTimeout(isScrolling);
            isScrolling = setTimeout(function() {
                 scrollFunction();
            }, 100);
        };
        function scrollFunction() {
            const scrollPosition = document.body.scrollTop || document.documentElement.scrollTop;
            const shouldShow = scrollPosition > 200;
            const isVisible = scrollToTopBtn.style.opacity === '1';

            if (shouldShow && !isVisible) {
                scrollToTopBtn.style.display = "block";
                void scrollToTopBtn.offsetWidth;
                scrollToTopBtn.style.opacity = '1';
            } else if (!shouldShow && isVisible) {
                scrollToTopBtn.style.opacity = '0';
                setTimeout(() => {
                    if (scrollToTopBtn.style.opacity === '0') {
                         scrollToTopBtn.style.display = "none";
                     }
                }, 300);
            }
        }
        scrollToTopBtn.addEventListener('click', function() { window.scrollTo({top: 0, behavior: 'smooth'}); });
        scrollFunction();
    }
    // --- TOP 버튼 로직 끝 ---


    // --- 서브 메뉴 호버 효과 (기존 유지) ---
    if (window.jQuery) {
        $(document).ready(function() {
            $(".main-menu > li").hover(
                function () {
                    $(this).children(".sub-menu").stop(true, true).slideDown(200);
                },
                function () {
                    $(this).children(".sub-menu").stop(true, true).slideUp(200);
                }
            );
        });
    } else {
        console.warn("jQuery not loaded, main menu hover effect skipped.");
    }
    // --- 서브 메뉴 호버 효과 끝 ---

});