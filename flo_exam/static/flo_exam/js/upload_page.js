// flo_exam/static/flo_exam/js/upload_page.js
console.log("FLO Exam - Upload Page JavaScript Loaded");

document.addEventListener('DOMContentLoaded', function() {
    const selectElement = document.getElementById('id_subject_area_0'); // 드롭다운 ID
    const textInputElement = document.getElementById('id_subject_area_1'); // 직접 입력 ID

    if (selectElement && textInputElement) {
        // 초기 placeholder 설정
        const initialSelectPlaceholder = "분야 선택"; // 또는 드롭다운의 첫 번째 옵션 텍스트
        const initialTextPlaceholder = textInputElement.placeholder || "직접 입력하세요";

        function updatePlaceholdersAndState() {
            if (textInputElement.value) { // 직접 입력 값이 있으면
                selectElement.value = ''; // 드롭다운 선택 해제
                // selectElement.disabled = true; // 선택: 드롭다운 비활성화
                // 드롭다운의 첫 번째 옵션(예: '--------')으로 재설정하여 시각적으로 선택 해제 표시
                if (selectElement.options.length > 0 && selectElement.options[0].value === '') {
                    selectElement.options[0].selected = true;
                }
                textInputElement.placeholder = initialTextPlaceholder;
            } else if (selectElement.value) { // 드롭다운 값이 선택되어 있으면
                // selectElement.disabled = false;
                const selectedText = selectElement.options[selectElement.selectedIndex].text;
                if (selectedText && selectedText !== '--------') { // '--------' 같은 빈 옵션 제외
                     textInputElement.placeholder = '선택됨: ' + selectedText;
                } else {
                    textInputElement.placeholder = initialTextPlaceholder;
                }
            } else { // 둘 다 값이 없으면
                // selectElement.disabled = false;
                textInputElement.placeholder = initialTextPlaceholder;
            }
        }

        // 드롭다운 변경 시
        selectElement.addEventListener('change', function() {
            if (this.value) { // 드롭다운에서 유효한 값 선택 시
                textInputElement.value = ''; // 직접 입력 칸을 비움
            }
            updatePlaceholdersAndState();
        });

        // 직접 입력 칸에 입력 시
        textInputElement.addEventListener('input', function() {
            updatePlaceholdersAndState();
        });
        
        // 직접 입력 칸에서 포커스 아웃 시 (입력 완료 후)
        textInputElement.addEventListener('blur', function() {
            updatePlaceholdersAndState();
        });


        // 페이지 로드 시 초기 상태 반영
        updatePlaceholdersAndState();
    }
});