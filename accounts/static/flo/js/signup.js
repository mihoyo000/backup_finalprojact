// ===== 공통 에러 메시지 처리 함수 =====
function showError(input, message) {
    const errorEl = input.closest('.form-group')?.querySelector('.error-message');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }
    input.classList.add('error');
}
function hideError(input) {
    const errorEl = input.closest('.form-group')?.querySelector('.error-message');
    if (errorEl) {
        errorEl.textContent = '';
        errorEl.style.display = 'none';
    }
    input.classList.remove('error');
}

// ====== 실시간 유효성 검사 함수 ======
function setupLiveValidation(fieldId, validateFunc) {
    const input = document.getElementById(fieldId);
    if (!input) return;
    input.addEventListener('input', function () {
        const msg = validateFunc(this.value);
        if (msg) {
            showError(this, msg);
        } else {
            hideError(this);
        }
    });
}

// ====== 필드별 유효성 검사 로직 ======
function usernameValidator(val) {
    if (!val) return '아이디를 입력해주세요.';
    if (!/^[a-zA-Z0-9]+$/.test(val)) return '아이디는 영문자와 숫자만 사용할 수 있습니다.';
    if (val.length < 4) return '아이디는 4자 이상 입력해주세요.';
    if (val.length > 20) return '아이디는 20자 이하로 입력해주세요.';
    return '';
}
function nicknameValidator(val) {
    if (!val) return '닉네임을 입력해주세요.';
    if (!/^[가-힣a-zA-Z0-9]+$/.test(val)) return '닉네임은 한글, 영문자, 숫자만 사용할 수 있습니다.';
    if (val.length < 2) return '닉네임은 2자 이상 입력해주세요.';
    if (val.length > 10) return '닉네임은 10자 이하로 입력해주세요.';
    return '';
}
function nameValidator(val) {
    if (!val) return '이름을 입력해주세요.';
    if (!/^[가-힣a-zA-Z]+$/.test(val)) return '이름은 한글과 영문자만 입력 가능합니다.';
    if (val.length < 2) return '이름은 2자 이상 입력해주세요.';
    if (val.length > 10) return '이름은 10자 이하로 입력해주세요.';
    return '';
}
function emailIdValidator(val) {
    if (!val) return '이메일을 입력해주세요.';
    if (val.length > 20) return '이메일 아이디는 20자 이하로 입력해주세요.';
    if (/\s/.test(val) || /@/.test(val)) return "공백과 '@'는 포함할 수 없습니다.";
    if (!/^[a-zA-Z0-9._-]+$/.test(val)) return '이메일 아이디는 영문자, 숫자, 특수문자(._-)만 사용할 수 있습니다.';
    return '';
}
function password1Validator(val) {
    if (!val) return '비밀번호를 입력해주세요.';
    if (val.length < 8) return '비밀번호는 8자 이상 입력해주세요.';
    if (!/(?=.*[a-zA-Z])(?=.*[0-9])/.test(val)) return '영문자와 숫자를 모두 포함해야 합니다.';
    return '';
}

// ====== 실시간 검사 적용 ======
document.addEventListener('DOMContentLoaded', function () {
    setupLiveValidation('username', usernameValidator);
    setupLiveValidation('nickname', nicknameValidator);
    setupLiveValidation('name', nameValidator);
    setupLiveValidation('email_id', emailIdValidator);
    setupLiveValidation('password1', password1Validator);

    // ===== 중복확인시 메시지 처리 및 스타일 =====
    window.checkDuplicate = function (type) {
        const inputField = document.getElementById(type);
        const value = inputField.value;
        if (!value) {
            showError(inputField, `${type === 'username' ? '아이디' : '닉네임'}를 입력해주세요.`);
            return;
        }
        fetch(`/accounts/check-duplicate/?field=${type}&value=${value}`)
            .then(response => response.json())
            .then(data => {
                if (!data.exists) {
                    inputField.classList.add('verified');
                    inputField.classList.remove('error');
                    inputField.setAttribute('data-verified', 'true');
                    hideError(inputField);
                    alert(data.message);
                } else {
                    inputField.classList.add('error');
                    inputField.classList.remove('verified');
                    inputField.removeAttribute('data-verified');
                    showError(inputField, data.message);
                }
            })
            .catch(error => {
                showError(inputField, '중복 확인 중 오류가 발생했습니다.');
            });
    };

    // 입력 중에는 중복확인 다시 해야 함
    ['username', 'nickname'].forEach(id => {
        const input = document.getElementById(id);
        if (!input) return;
        input.addEventListener('input', function () {
            this.removeAttribute('data-verified');
            this.classList.remove('verified');
        });
    });

    // ===== 이메일 관련 요소 =====
    const emailId = document.getElementById('email_id');
    const emailDomain = document.getElementById('email_domain');

    // 이메일 중복확인
    window.checkEmailDuplicate = function() {
        if (!emailId || !emailDomain) return;
        
        const fullEmail = emailId.value + '@' + emailDomain.value;

        if (!emailId.value) {
            showError(emailId, '이메일을 입력해주세요.');
            return;
        }
        if (!emailDomain.value) {
            showError(emailId, '이메일 도메인을 선택해주세요.');
            return;
        }

        fetch(`/accounts/check-duplicate/?field=email&value=${fullEmail}`)
            .then(response => response.json())
            .then(data => {
                if (!data.exists) {
                    emailId.classList.add('verified');
                    emailId.classList.remove('error');
                    emailId.setAttribute('data-verified', 'true');
                    hideError(emailId);
                    alert(data.message);
                } else {
                    emailId.classList.add('error');
                    emailId.classList.remove('verified');
                    emailId.removeAttribute('data-verified');
                    showError(emailId, data.message);
                }
            })
            .catch(error => {
                showError(emailId, '중복 확인 중 오류가 발생했습니다.');
            });
    };

    // 이메일 입력 시 중복확인 상태 초기화
    if (emailId) {
        emailId.addEventListener('input', function() {
            this.removeAttribute('data-verified');
            this.classList.remove('verified');
        });
    }

    // 이메일 도메인 변경 시 중복확인 상태 초기화
    if (emailDomain) {
        emailDomain.addEventListener('change', function() {
            if (emailId) {
                emailId.removeAttribute('data-verified');
                emailId.classList.remove('verified');
            }
        });
    }

    // ===== 이메일 도메인 자동 완성 =====
    if (emailDomain && emailId) {
        emailDomain.addEventListener('change', function () {
            const currentEmail = emailId.value.split('@')[0];
            emailId.value = currentEmail + '@' + this.value;
        });
    }

    // ===== 약관 전체 동의 체크 =====
    const allAgreeCheckbox = document.getElementById('all-agree');
    const agreeCheckboxes = document.querySelectorAll('.agree-checkbox:not(#all-agree)');
    if (allAgreeCheckbox) {
        allAgreeCheckbox.addEventListener('change', function () {
            agreeCheckboxes.forEach(cb => cb.checked = this.checked);
        });
        agreeCheckboxes.forEach(cb => {
            cb.addEventListener('change', function () {
                allAgreeCheckbox.checked = Array.from(agreeCheckboxes).every(cb => cb.checked);
            });
        });
    }

    // ===== 비밀번호 강도, 일치 확인 (password2) =====
    const pw1 = document.getElementById('password1');
    const pw2 = document.getElementById('password2');
    const strength1 = document.querySelector('#password1 ~ .repw-strength');
    const matchMessage = document.querySelector('.password-match-message');

    const getStrength = (password) => {
        if (!password) return 'none';
        const strongRegex = /^(?=.*[a-zA-Z])(?=.*[0-9])(?=.*[!@#$%^&*()\-_=+\[\]{};:,.<>?]).{10,}$/;
        const mediumRegex = /^(?=.*[a-zA-Z])(?=.*[0-9]).{8,}$/;
        if (strongRegex.test(password)) return 'strong';
        if (mediumRegex.test(password)) return 'medium';
        return 'weak';
    };

    const updateStrengthDisplay = (el, strength) => {
        if (!el) return;
        el.classList.remove('weak', 'medium', 'strong');
        switch (strength) {
            case 'strong':
                el.classList.add('strong');
                el.textContent = '강도: 강함';
                break;
            case 'medium':
                el.classList.add('medium');
                el.textContent = '강도: 중간';
                break;
            case 'weak':
                el.classList.add('weak');
                el.textContent = '강도: 약함';
                break;
            default:
                el.textContent = '강도: 없음';
        }
    };

    const checkMatch = () => {
        if (!pw1 || !pw2 || !matchMessage) return;
        const val1 = pw1.value;
        const val2 = pw2.value;
        if (!val1 || !val2) {
            matchMessage.textContent = '';
            pw2.setCustomValidity('');
            return;
        }
        if (val1 !== val2) {
            matchMessage.textContent = '비밀번호가 일치하지 않습니다.';
            pw2.setCustomValidity('비밀번호가 일치하지 않습니다.');
        } else {
            matchMessage.textContent = '';
            pw2.setCustomValidity('');
        }
    };

    if (pw1) {
        pw1.addEventListener('input', function () {
            const strength = getStrength(this.value);
            updateStrengthDisplay(strength1, strength);
            checkMatch();
        });
        updateStrengthDisplay(strength1, getStrength(pw1.value));
    }
    if (pw2) {
        pw2.addEventListener('input', checkMatch);
    }

    // ===== 폼 제출 전 최종 검증 =====
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            let hasError = false;
            const errorMessages = [];
            // 실시간 유효성 체크에 걸린 필드가 있다면 막음
            ['username', 'nickname', 'name', 'email_id', 'password1'].forEach(fieldId => {
                const input = document.getElementById(fieldId);
                if (!input) return;
                const validatorMap = {
                    'username': usernameValidator,
                    'nickname': nicknameValidator,
                    'name': nameValidator,
                    'email_id': emailIdValidator,
                    'password1': password1Validator,
                };
                const msg = validatorMap[fieldId](input.value);
                if (msg) {
                    showError(input, msg);
                    hasError = true;
                }
            });

            // 중복확인 체크
            const username = document.getElementById('username');
            const nickname = document.getElementById('nickname');
            if (!username.getAttribute('data-verified')) {
                showError(username, '아이디 중복 확인이 필요합니다.');
                hasError = true;
            }
            if (!nickname.getAttribute('data-verified')) {
                showError(nickname, '닉네임 중복 확인이 필요합니다.');
                hasError = true;
            }

            // 약관 동의 체크
            const requiredCheckboxes = document.querySelectorAll('.agree-checkbox[required]');
            const allChecked = Array.from(requiredCheckboxes).every(cb => cb.checked);
            if (!allChecked) {
                errorMessages.push('필수 약관에 모두 동의해주세요.');
                hasError = true;
            }

            // 이메일 중복확인 체크
            if (!emailId.getAttribute('data-verified')) {
                showError(emailId, '이메일 중복 확인이 필요합니다.');
                hasError = true;
            }

            // 이메일 도메인 선택 체크
            if (!emailDomain.value) {
                showError(emailId, '이메일 도메인을 선택해주세요.');
                hasError = true;
            }

            if (hasError) {
                if (errorMessages.length) alert(errorMessages.join('\n'));
                return;
            }
            this.submit();
        });
    }
});
