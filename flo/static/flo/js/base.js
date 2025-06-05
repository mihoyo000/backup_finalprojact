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

        // 프로필 이미지 요소 추가
        const userProfileImage = document.getElementById('user-profile-image');

        const getCurrentThemeSetting = () => localStorage.getItem('theme') || 'light'; // 기본값을 'light'로 명시

        // 현재 body에 실제로 적용된 테마를 가져오는 헬퍼 함수 추가
        const getCurrentAppliedTheme = () => {
            if (body.classList.contains('theme-dark')) {
                return 'dark';
            }
            return 'light'; // 기본값 또는 theme-light
        };

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

            // 프로필 이미지 변경 로직 추가
            if (userProfileImage && window.defaultProfileImagePaths) {
                // `base.html`에서 `<img id="user-profile-image" data-has-custom-image="...">` 와 같이 설정되어 있어야 함
                const hasCustomImage = userProfileImage.dataset.hasCustomImage === 'true';

                if (!hasCustomImage) { // 사용자가 직접 업로드한 이미지가 아닐 때만 기본 이미지 변경
                    let newProfileSrc = '';
                    // getCurrentAppliedTheme()를 사용하여 실제 body에 적용된 테마를 기준으로 결정
                    const appliedTheme = getCurrentAppliedTheme();

                    if (appliedTheme === 'dark' && window.defaultProfileImagePaths.dark) {
                        newProfileSrc = window.defaultProfileImagePaths.dark;
                    } else if (window.defaultProfileImagePaths.light) { // 기본은 라이트
                        newProfileSrc = window.defaultProfileImagePaths.light;
                    }

                    if (newProfileSrc && userProfileImage.src !== newProfileSrc) {
                        userProfileImage.src = newProfileSrc;
                    }
                }
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

    // ▼▼▼ 추가 시작 ▼▼▼ (반응형 헤더 로직)
    const navbarToggler = document.querySelector('.navbar-toggler');
    const mainNav = document.getElementById('mainNav');  // 스크롤 대상 컨테이너
    const DESKTOP_BREAKPOINT = 992; // CSS의 @media (min-width: 992px)와 일치
    

    // 햄버거 메뉴 토글 (메인 네비게이션 열고 닫기)
    if (navbarToggler && mainNav) {
        navbarToggler.addEventListener('click', function() {
            const isNavOpen = mainNav.classList.toggle('show');
            this.classList.toggle('active', isNavOpen);

            // 모바일 전용 섹션 가져오기
            const mobileProfileSection = mainNav.querySelector('.nav-mobile-profile-section');
            const mobileThemeSection = mainNav.querySelector('.nav-mobile-theme-section');

            if (isNavOpen) {
                mainNav.scrollTop = 0;
                // 모바일 뷰이고, 메뉴가 열렸을 때만 해당 섹션들 표시 (CSS로도 가능)
                if (window.innerWidth < DESKTOP_BREAKPOINT) {
                    if (mobileProfileSection) mobileProfileSection.style.display = 'block'; // 또는 'flex'
                    if (mobileThemeSection) mobileThemeSection.style.display = 'block';   // 또는 'flex'
                }
                // ▼▼▼ 추가: 햄버거 메뉴가 열릴 때, 다른 드롭다운 z-index 초기화 ▼▼▼
                document.querySelectorAll('.header-right-controls .dropdown-menu.show-over-main-nav').forEach(ddMenu => {
                    ddMenu.classList.remove('show-over-main-nav');
                });
                // ▲▲▲ 추가 끝 ▲▲▲
            } else {
                // 메뉴 닫힐 때 모바일 섹션 숨김 (CSS로도 가능)
                if (mobileProfileSection) mobileProfileSection.style.display = 'none';
                if (mobileThemeSection) mobileThemeSection.style.display = 'none';
                mainNav.querySelectorAll('.sub-menu.open').forEach(openSubMenu => {
                    openSubMenu.classList.remove('open');
                    const parentAnchor = openSubMenu.previousElementSibling;
                    if (parentAnchor && parentAnchor.tagName === 'A') {
                        parentAnchor.classList.remove('open');
                    }
                });
            }
        });
    }

    // 모바일/태블릿에서 서브메뉴 토글 (data-bs-toggle="submenu" 사용)
    const submenuParentAnchors = document.querySelectorAll('.main-menu > li > a[data-bs-toggle="submenu"]');
    submenuParentAnchors.forEach(anchor => {
        anchor.addEventListener('click', function(event) {
            if (window.innerWidth >= DESKTOP_BREAKPOINT) { // 데스크톱에서는 JS 토글 방지
                return; 
            }

            event.preventDefault(); 
            event.stopPropagation(); 

            const subMenu = this.nextElementSibling; 
            if (subMenu && subMenu.classList.contains('sub-menu')) {
                const parentLi = this.parentElement; 
                const currentlyOpen = subMenu.classList.contains('open');

                // 다른 열려있는 서브메뉴 닫기 (하나만 열리도록)
                if (!currentlyOpen) { 
                    parentLi.parentElement.querySelectorAll('.sub-menu.open').forEach(otherOpenSubMenu => {
                        if (otherOpenSubMenu !== subMenu) {
                            otherOpenSubMenu.classList.remove('open');
                            const otherAnchor = otherOpenSubMenu.previousElementSibling;
                            if (otherAnchor && otherAnchor.tagName === 'A') {
                                otherAnchor.classList.remove('open');
                            }
                        }
                    });
                }

                // 현재 클릭한 서브메뉴 토글
                subMenu.classList.toggle('open'); 
                this.classList.toggle('open', subMenu.classList.contains('open')); 
            }
        });
    });

    // 창 크기 변경 시 처리 (데스크톱 <-> 모바일 전환)
    window.addEventListener('resize', function() {
        if (window.innerWidth >= DESKTOP_BREAKPOINT) {
            // 데스크톱 뷰로 전환 시: 열려있는 모바일 메뉴(햄버거) 닫기
            if (mainNav && mainNav.classList.contains('show')) {
                mainNav.classList.remove('show');
                if (navbarToggler) navbarToggler.classList.remove('active');
            }
            // 데스크톱에서는 JS로 열린 서브메뉴들(.open) 닫기 (호버로 동작하므로)
            document.querySelectorAll('.main-menu .sub-menu.open').forEach(subMenu => {
                subMenu.classList.remove('open');
                const parentAnchor = subMenu.previousElementSibling;
                if (parentAnchor && parentAnchor.tagName === 'A') {
                    parentAnchor.classList.remove('open');
                }
            });
        } else {
            // 모바일 뷰로 전환 시: (특별히 할 일 없음, jQuery 호버는 아래에서 비활성화됨)
        }
    });
    // ▲▲▲ 추가 끝 ▲▲▲ (반응형 헤더 로직)

    // ▼▼▼ 추가: 헤더 오른쪽 컨트롤 드롭다운 z-index 관리 ▼▼▼
    const headerRightControlsDropdowns = document.querySelectorAll('.header-right-controls .dropdown');

    headerRightControlsDropdowns.forEach(dropdown => {
        const dropdownToggle = dropdown.querySelector('[data-bs-toggle="dropdown"]');
        const dropdownMenu = dropdown.querySelector('.dropdown-menu');

        if (dropdownToggle && dropdownMenu) {
            // Bootstrap의 'shown.bs.dropdown' 이벤트는 드롭다운 메뉴가 완전히 표시된 후에 발생합니다.
            dropdownToggle.addEventListener('shown.bs.dropdown', function () {
                if (mainNav && mainNav.classList.contains('show') && window.innerWidth < DESKTOP_BREAKPOINT) {
                    dropdownMenu.classList.add('show-over-main-nav');
                }
            });

            // Bootstrap의 'hidden.bs.dropdown' 이벤트는 드롭다운 메뉴가 완전히 숨겨진 후에 발생합니다.
            dropdownToggle.addEventListener('hidden.bs.dropdown', function () {
                dropdownMenu.classList.remove('show-over-main-nav');
            });
        }
    });
    // ▲▲▲ 추가 끝 ▲▲▲

    // --- TOP 버튼 로직 ---
    const scrollToTopBtn = document.getElementById('scroll-to-top');
    // ▼▼▼ 수정 ▼▼▼ (fullPage.js 사용 여부 체크를 좀 더 명확하게)
    const isFullPageActive = typeof fullpage_api !== 'undefined' && fullpage_api.getActiveSection;

    if (scrollToTopBtn && !isFullPageActive) { // fullPage.js가 활성화되지 않았을 때만 이 스크롤 로직 사용
    // ▲▲▲ 수정 ▲▲▲
        let isScrolling;
        const scrollFunction = () => {
            const scrollPosition = document.body.scrollTop || document.documentElement.scrollTop;
            const shouldShow = scrollPosition > 200;
            const isVisible = scrollToTopBtn.style.opacity === '1';

            if (shouldShow && !isVisible) {
                scrollToTopBtn.style.display = "block";
                requestAnimationFrame(() => { // 다음 프레임에서 opacity 변경하여 애니메이션 트리거
                    scrollToTopBtn.style.opacity = '1';
                });
            } else if (!shouldShow && isVisible) {
                scrollToTopBtn.style.opacity = '0';
                setTimeout(() => {
                    if (scrollToTopBtn.style.opacity === '0') {
                         scrollToTopBtn.style.display = "none";
                     }
                }, 300); // CSS transition 시간과 일치
            }
        };
        window.addEventListener('scroll', function() {
            window.clearTimeout(isScrolling);
            isScrolling = setTimeout(scrollFunction, 100);
        });
        scrollToTopBtn.addEventListener('click', () => window.scrollTo({top: 0, behavior: 'smooth'}));
        scrollFunction(); // 초기 로드 시 호출
    } else if (scrollToTopBtn && isFullPageActive) {
        // fullPage.js 사용 시 TOP 버튼은 fullPage.js API로 제어 (예: 첫 번째 섹션으로 이동)
        scrollToTopBtn.addEventListener('click', function() {
            fullpage_api.moveTo(1);
        });
        // fullPage.js에서는 첫 번째 섹션이 아니면 TOP 버튼을 보여줄 수 있음
        // 이 부분은 fullPage.js의 afterLoad 콜백에서 처리하는 것이 더 적합
        // 여기서는 기본적으로 숨김 처리하고, fullPage.js 설정에서 제어
        scrollToTopBtn.style.display = 'none';
    }
    // --- TOP 버튼 로직 끝 ---


    // --- 서브 메뉴 호버 효과 ---
    // ▼▼▼ 수정 ▼▼▼ (jQuery 사용 시, 데스크톱에서만 호버 작동하도록 조건 추가)
    if (window.jQuery) {
        function initializeMainMenuHover() {
            if (window.innerWidth >= DESKTOP_BREAKPOINT) {
                $(".main-menu > li").each(function() {
                    // 이미 호버 이벤트가 바인딩되어 있다면 중복 방지 (선택적, off로도 충분할 수 있음)
                    // $(this).off('mouseenter.desktopHover mouseleave.desktopHover');

                    // 데스크톱에서만 호버 적용
                    $(this).on('mouseenter.desktopHover', function () {
                        // 모바일에서 JS로 열린 상태(.open)가 아니라면 호버로 열기
                        if (!$(this).children('a[data-bs-toggle="submenu"]').hasClass('open')) {
                            $(this).children(".sub-menu").stop(true, true).slideDown(200);
                        }
                    }).on('mouseleave.desktopHover', function () {
                        if (!$(this).children('a[data-bs-toggle="submenu"]').hasClass('open')) {
                            $(this).children(".sub-menu").stop(true, true).slideUp(200);
                        }
                    });
                });
            } else {
                // 모바일 뷰: 데스크톱용 호버 이벤트 제거
                $(".main-menu > li").off('mouseenter.desktopHover mouseleave.desktopHover');
                // 모바일에서는 CSS와 JS 클릭으로 제어하므로, jQuery로 인한 display 변경 초기화
                $(".main-menu > li > .sub-menu").css('display', '');
            }
        }
        initializeMainMenuHover();
        $(window).on('resize', initializeMainMenuHover);
    } else {
        console.warn("jQuery not loaded, main menu hover effect skipped.");
    }
    // ▲▲▲ 수정 ▲▲▲
    // --- 서브 메뉴 호버 효과 끝 ---

});