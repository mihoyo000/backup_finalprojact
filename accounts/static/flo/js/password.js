document.addEventListener('DOMContentLoaded', () => {
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
    pw1.addEventListener('input', function() {
      const strength = getStrength(this.value);
      updateStrengthDisplay(strength1, strength);
      checkMatch();
    });

    updateStrengthDisplay(strength1, getStrength(pw1.value));
  }

  if (pw2) {
    pw2.addEventListener('input', checkMatch);
  }
});

// 비밀번호 변경 취소 확인
function confirmCancel() {
  if (confirm('비밀번호 변경을 취소하시겠습니까?')) {
    window.location.href = "/";
  }
}

// 비밀번호 변경 완료 확인
function confirmSubmit(event) {
  event.preventDefault();
  if (confirm('비밀번호 변경이 완료되었습니다.')) {
    document.querySelector('form').submit();
  }
  return false;
}
