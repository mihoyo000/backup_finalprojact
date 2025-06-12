$(document).ready(function () {
    const nav = $('.nf-settings-tabs');
    const line = $('<div />').addClass('line');
    line.appendTo(nav);

    let active = nav.find('.active');
    let pos = 0;
    let wid = 0;

    if (active.length) {
        const tabItem = active.find('.nf-tab-item');
        pos = active.position().left;
        wid = tabItem.outerWidth();
        line.css({
            left: pos,
            width: wid
        });

        // 모든 탭 콘텐츠를 숨기고 해당 탭 내용만 보여줌
        $('.nf-tab-content').hide();
        const targetId = tabItem.attr('href');
        $(targetId).show();
    }

    nav.find('ul li a').click(function (e) {
        e.preventDefault();
        if (!$(this).parent().hasClass('active') && !nav.hasClass('animate')) {
            nav.addClass('animate');

            const _this = $(this);
            const parent = _this.parent();
            const tabItem = _this;

            nav.find('ul li').removeClass('active');

            const position = parent.position();
            const width = tabItem.outerWidth();

            if (position.left >= pos) {
                line.animate({
                    width: ((position.left - pos) + width)
                }, 300, function () {
                    line.animate({
                        width: width,
                        left: position.left
                    }, 150, function () {
                        nav.removeClass('animate');
                    });
                    parent.addClass('active');
                });
            } else {
                line.animate({
                    left: position.left,
                    width: ((pos - position.left) + wid)
                }, 300, function () {
                    line.animate({
                        width: width
                    }, 150, function () {
                        nav.removeClass('animate');
                    });
                    parent.addClass('active');
                });
            }

            pos = position.left;
            wid = width;

            // 탭 내용 전환
            const target = $(_this.attr('href'));
            $('.nf-tab-content').hide();
            target.show();
        }
    });
});


document.addEventListener("DOMContentLoaded", function () {
  const preview = document.getElementById("profileImagePreview");
  const fileInput = document.getElementById("profile_image");
  const profileForm = document.getElementById("profileForm");
  const resetBtn = document.getElementById("resetProfileImage");

  // 1. 초기 이미지 설정 (캐시 우회용) $
  if (preview) {
    const imageUrl = preview.getAttribute("data-image-url");
    if (imageUrl) {
      preview.style.backgroundImage = `url('${imageUrl}?v=${Date.now()}')`; // $
    }
  }

  // 2. 이미지 업로드 시 미리보기 적용
  if (fileInput && preview) {
    fileInput.addEventListener("change", function () {
      const file = this.files[0];
      if (file && file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = function (e) {
          preview.style.backgroundImage = `url(${e.target.result})`;
        };
        reader.readAsDataURL(file);

        // reset hidden input 제거 (중복 방지) $
        const resetInput = document.getElementById("reset_profile_image_flag");
        if (resetInput) resetInput.remove(); // $
      } else {
        alert("이미지 파일만 업로드할 수 있습니다.");
        fileInput.value = "";
      }
    });
  }

  // 3. 기본 이미지로 변경 버튼 처리
  if (resetBtn && preview) {
    resetBtn.addEventListener("click", function (e) {
      e.preventDefault(); // $ form submit 막기

      if (confirm("기본 이미지로 변경하시겠습니까?")) {
        const defaultUrl = "/static/flo/images/icons/profile/default_profile_light.png";
        preview.style.backgroundImage = `url('${defaultUrl}?v=${Date.now()}')`; // $
        preview.setAttribute("data-image-url", defaultUrl);
        fileInput.value = "";

        // reset flag hidden input 추가
        let hiddenInput = document.getElementById("reset_profile_image_flag");
        if (!hiddenInput) {
          hiddenInput = document.createElement("input");
          hiddenInput.type = "hidden";
          hiddenInput.name = "reset_profile_image";
          hiddenInput.id = "reset_profile_image_flag";
          profileForm.appendChild(hiddenInput);
        }
        hiddenInput.value = "true"; // $
      }
    });
  }

  // 4. 폼 AJAX 제출 처리
  if (profileForm) {
    profileForm.addEventListener("submit", function (e) {
      e.preventDefault();

      const formData = new FormData(profileForm);
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
      preview.classList.add("loading");

      fetch("/accounts/settings/profile/", {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest"
        }
      })
        .then((response) => response.json())
        .then((data) => {
          preview.classList.remove("loading");

          if (data.success) {
            const newImageUrl = data.new_image_url + "?v=" + Date.now();
            preview.style.backgroundImage = `url('${newImageUrl}')`;
            preview.setAttribute("data-image-url", newImageUrl);

            const profileImages = document.querySelectorAll(".profile-image-wrapper img");
            profileImages.forEach((img) => {
              img.src = newImageUrl;
              if (data.has_custom_image) {
                img.classList.remove("default-avatar");
              } else {
                img.classList.add("default-avatar");
              }
            });

            // reset 아닐 때만 alert 출력 $
            const resetFlag = profileForm.querySelector('[name="reset_profile_image"]');
            if (!resetFlag || resetFlag.value !== "true") {
              alert(data.message); // $
            }
          } else {
            alert(data.message);
          }
        })
        .catch((error) => {
          preview.classList.remove("loading");
          console.error("Error:", error);
          alert("프로필 업데이트 중 오류가 발생했습니다.");
        });
    });
  }
});


document.addEventListener("DOMContentLoaded", function () {
  const preview = document.getElementById("profileImagePreview");
  if (preview) {
    const imageUrl = preview.getAttribute("data-image-url");
    if (imageUrl) {
      preview.style.backgroundImage = `url('${imageUrl}?v=${Date.now()}')`;
    }
  }
});

//이메일 변경하기 버튼  0611
document.addEventListener('DOMContentLoaded', function() {
  const changeBtn = document.getElementById('changeEmailBtn');
  const emailChangeArea = document.getElementById('emailChangeArea');
  const overlay = document.getElementById('pending-overlay');

  if (changeBtn && emailChangeArea) {
    changeBtn.addEventListener('click', function() {
      // 버튼이 "이메일 변경하기" 상태면 → 입력필드 보여주고 텍스트 "취소"로
      if (emailChangeArea.style.display === 'none' || emailChangeArea.style.display === '') {
        emailChangeArea.style.display = 'flex';
        changeBtn.textContent = '취소';
      }
      // 버튼이 "취소" 상태면 → 입력필드 숨기고 텍스트 다시 "이메일 변경하기"로
      else {
        emailChangeArea.style.display = 'none';
        changeBtn.textContent = '이메일 변경하기';
        // 입력필드 값도 초기화할 경우 아래 주석 해제
        // document.getElementById('new_email').value = '';
      }
    });
  }
});

$('#verifyEmailBtn').on('click', function() {
  let email = $('#new_email').val();
  if(!email) {
    alert('이메일을 입력해주세요');
    return;
  }
  overlay.style.display = 'flex';
  resendBtn.disabled = true;
  
  $.post('/accounts/send_verification_email/', {
      new_email: email,
      csrfmiddlewaretoken: $('[name=csrfmiddlewaretoken]').val()
    })
    .done(function(data){
      if(data.result === 'ok') {
        // 바로 리디렉션
        window.location.href = '/accounts/email-pending/';
      } else {
        alert('오류가 발생했습니다. 다시 시도해 주세요.');
      }
    });
});
