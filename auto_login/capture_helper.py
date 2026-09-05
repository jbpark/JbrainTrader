import pyautogui
import time
import os

def capture_login_elements():
    """
    로그인에 필요한 이미지들을 5초 후에 캡처합니다.
    사용자는 5초 이내에 로그인 창을 띄워두어야 합니다.
    """
    if not os.path.exists('images'):
        os.makedirs('images')
        
    print("5초 후에 캡처를 시작합니다. 로그인 창을 화면에 띄워주세요.")
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    # 이 부분은 사용자가 직접 좌표를 지정하거나 
    # 전체 화면에서 잘라내는 방식으로 가이드가 필요합니다.
    # 여기서는 안내 메시지만 출력합니다.
    print("현재는 자동 캡처 기능이 구현되지 않았습니다.")
    print("Windows의 '캡처 도구'(Snipping Tool)를 사용하여 다음 파일명으로 images 폴더에 저장해주세요:")
    print("1. mock_checkbox.png - 모의투자 체크박스 부분")
    print("2. real_checkbox.png - 실거래 체크박스 부분")
    print("3. login_button.png - 로그인 버튼 부분")

if __name__ == "__main__":
    capture_login_elements()
