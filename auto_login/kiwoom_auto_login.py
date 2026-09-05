import time
import os
import sys

# 단독 실행 시 auto_login 폴더를 sys.path에 추가
_AUTO_LOGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _AUTO_LOGIN_DIR not in sys.path:
    sys.path.insert(0, _AUTO_LOGIN_DIR)

import config
import win32gui
import win32con
import win32api
import ctypes

# ============================================================
# CLI 인자로 모드 오버라이드 (--mock / --real)
# api_server.py가 subprocess로 실행할 때 모드를 전달합니다.
# ============================================================
if "--real" in sys.argv:
    config.IS_MOCK_INVESTMENT = False
    print("[AutoLogin] 모드 오버라이드: 실거래 (--real)")
elif "--mock" in sys.argv:
    config.IS_MOCK_INVESTMENT = True
    print("[AutoLogin] 모드 오버라이드: 모의투자 (--mock)")
else:
    # 인자 없음: .env의 KIWOOM_IS_MOCK 값 사용
    print(f"[AutoLogin] 모드: {'모의투자' if config.IS_MOCK_INVESTMENT else '실거래'} (.env 기준)")


# ============================================================
# 컨트롤 ID 정의 (debug_login.py 분석 결과)
# ============================================================
CTRL_ID_USERID   = 1000  # 고객 ID (Edit)
CTRL_ID_PASSWORD = 1001  # 비밀번호 (Edit, ES_PASSWORD)
CTRL_ID_CERTPW   = 1002  # 인증비밀번호 (Edit, ES_PASSWORD)
CTRL_ID_LOGIN_BTN = 1     # 로그인 버튼 (Button)
CTRL_ID_MOCK_CHK = 1005  # 모의투자 접속 체크박스 (Button)

WM_SETTEXT   = 0x000C
BM_CLICK     = 0x00F5
BM_GETCHECK  = 0x00F0  # 체크박스 상태 조회
BST_CHECKED  = 1
BST_UNCHECKED = 0


def find_child_by_ctrl_id(parent_hwnd, ctrl_id):
    """부모 창에서 특정 ctrl_id를 가진 자식 컨트롤의 hwnd를 반환합니다."""
    result = [None]
    def callback(child_hwnd, _):
        if win32gui.GetDlgCtrlID(child_hwnd) == ctrl_id:
            result[0] = child_hwnd
            return False  # 찾았으면 중단
    try:
        win32gui.EnumChildWindows(parent_hwnd, callback, None)
    except:
        pass
    return result[0]


def close_popup_by_title(keyword, timeout=3):
    """창 제목에 keyword가 포함된 팝업을 찾아 닫습니다."""
    user32 = ctypes.windll.user32
    found = False

    def try_close(hwnd):
        nonlocal found
        title = win32gui.GetWindowText(hwnd)
        print(f"  → 팝업 닫기: [{title}]")
        
        # 자식 버튼 찾아서 BM_CLICK
        def enum_child(child_hwnd, _):
            if win32gui.GetClassName(child_hwnd) == "Button":
                user32.SendMessageW(child_hwnd, BM_CLICK, 0, 0)
                return False
        try:
            win32gui.EnumChildWindows(hwnd, enum_child, None)
        except:
            pass
        time.sleep(0.5)
        
        # 아직 열려있으면 WM_CLOSE
        if win32gui.IsWindow(hwnd):
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        found = True

    start = time.time()
    while time.time() - start < timeout:
        def enum_all(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd): return
            if keyword in win32gui.GetWindowText(hwnd):
                try_close(hwnd)
        win32gui.EnumWindows(enum_all, None)
        if found: break
        time.sleep(0.5)
    
    return found


def handle_popups():
    """업그레이드 확인 등 방해되는 팝업을 닫습니다."""
    print("팝업창 체크 중...")
    if close_popup_by_title("업그레이드 확인", timeout=3):
        print("업그레이드 팝업을 닫았습니다.")
        time.sleep(2)


def send_click_to_control(hwnd):
    """
    컨트롤에 클릭을 전송합니다.
    1차: WM_LBUTTONDOWN/UP (창 내부 상대좌표로 직접 전송, DPI 무관)
    2차: pyautogui 물리 클릭 (폴백)
    """
    # 컨트롤의 크기를 구해서 중심 상대좌표 계산
    rect = win32gui.GetWindowRect(hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    cx = w // 2
    cy = h // 2
    lparam = (cy << 16) | (cx & 0xFFFF)  # MAKELONG(cx, cy)

    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP   = 0x0202
    MK_LBUTTON     = 0x0001

    print(f"    → WM_LBUTTON 전송 (hwnd={hwnd}, rel_center=({cx},{cy}))")
    win32api.SendMessage(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    time.sleep(0.05)
    win32api.SendMessage(hwnd, WM_LBUTTONUP, 0, lparam)
    time.sleep(0.3)


def _force_foreground(hwnd):
    """
    Alt keybd_event 트릭으로 SetForegroundWindow를 안정적으로 호출합니다.
    서브프로세스에서도 포커스를 가져올 수 있습니다.
    """
    try:
        user32 = ctypes.windll.user32
        # Alt down/up 트릭: Windows가 포커스 제약을 일시 해제
        user32.keybd_event(0x12, 0, 0, 0)       # Alt down
        user32.keybd_event(0x12, 0, 0x0002, 0)  # Alt up
        time.sleep(0.05)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        return True
    except Exception as e:
        print(f"    → SetForegroundWindow 실패: {e}")
        try:
            ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
            ctypes.windll.user32.BringWindowToTop(hwnd)
            time.sleep(0.1)
        except:
            pass
        return False


def send_text_to_control(hwnd, text, login_hwnd=None):
    """
    콘트롤에 텍스트를 입력합니다.

    전략:
      - 일반 필드: WM_SETTEXT 시도 → 성공 시 반환, 실패 시 클립보드 폴백
      - ES_PASSWORD 필드: WM_SETTEXT는 Windows 보안정리으로 외부 프로세스에서 조용히 차단 →
                           물리 클릭 + 클립보드(pyperclip) + Ctrl+V 사용
    """
    import win32con

    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    is_password = bool(style & 0x20)

    if is_password:
        # ES_PASSWORD 필드: WM_SETTEXT 먼저 시도 (관리자 권한에서는 동작할 수 있음)
        win32api.SendMessage(hwnd, WM_SETTEXT, 0, "")
        time.sleep(0.1)
        win32api.SendMessage(hwnd, WM_SETTEXT, 0, text)
        time.sleep(0.2)

        length = win32api.SendMessage(hwnd, 0x000E, 0, 0)  # WM_GETTEXTLENGTH
        print(f"    → ES_PASSWORD 필드 WM_GETTEXTLENGTH = {length}")

        if length > 0:
            print(f"    → WM_SETTEXT 성공! (관리자 권한으로 입력 완료)")
            return True

        # WM_SETTEXT 실패 → 클립보드 폴백
        print(f"    → WM_SETTEXT 차단됨. 클립보드 붙여넣기 방식으로 전환...")
        return _paste_via_clipboard(hwnd, text, login_hwnd)

    # 일반 필드: WM_SETTEXT 시도
    win32api.SendMessage(hwnd, WM_SETTEXT, 0, "")
    time.sleep(0.1)
    win32api.SendMessage(hwnd, WM_SETTEXT, 0, text)
    time.sleep(0.2)

    length = win32api.SendMessage(hwnd, 0x000E, 0, 0)  # WM_GETTEXTLENGTH
    if length > 0:
        print(f"    → WM_SETTEXT 성공 (길이: {length})")
        return True

    print(f"    → WM_SETTEXT 실패. 클립보드 폴백...")
    return _paste_via_clipboard(hwnd, text, login_hwnd)


def _paste_via_clipboard(hwnd, text, login_hwnd=None):
    """
    클립보드(pyperclip) + 물리 클릭 + Ctrl+V로 콘트롤에 텍스트를 붙여넣습니다.
    ES_PASSWORD 제약과 UIPI를 모두 우회하는 가장 안정적인 방법입니다.
    """
    try:
        import pyperclip
        import pyautogui
    except ImportError as e:
        print(f"    \u2192 필수 패키지 미설치: {e}")
        return False

    try:
        # 1. 로그인 창을 전경으로 가져오기
        target = login_hwnd if login_hwnd else (win32gui.GetParent(hwnd) or hwnd)
        _force_foreground(target)

        # 2. 콘트롤 중앙 클릭 (포커스 이동)
        rect = win32gui.GetWindowRect(hwnd)
        cx = (rect[0] + rect[2]) // 2
        cy = (rect[1] + rect[3]) // 2
        pyautogui.click(cx, cy)
        time.sleep(0.25)

        # 3. 기존 내용 전체 선택
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)

        # 4. 클립보드에 복사 후 붙여넣기
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.25)

        # 5. 보안을 위해 클립보드 비우기
        pyperclip.copy('')

        print(f"    \u2192 클립보드 붙여넣기 완료")
        return True
    except Exception as e:
        print(f"    \u2192 클립보드 붙여넣기 실패: {e}")
        return False


def is_checkbox_checked(login_hwnd, mock_chk_hwnd):
    """
    체크박스 체크 여부를 신뢰할 수 있는 방법으로 판별합니다.
    0차: BM_GETCHECK Win32 메시지 (가장 신뢰도 높음)
    1차: pywinauto UIA 백엔드로 ToggleState 읽기
    2차: 체크박스 중앙 픽셀 밝기 비교
    """
    # --- 방법 0: BM_GETCHECK (Win32 직접 조회 - 가장 신뢰도 높음) ---
    try:
        result = win32api.SendMessage(mock_chk_hwnd, BM_GETCHECK, 0, 0)
        print(f"    → BM_GETCHECK 결과: {result} (1=체크됨, 0=해제됨)")
        if result in (BST_CHECKED, BST_UNCHECKED):
            return result == BST_CHECKED
        print(f"    → BM_GETCHECK 예상치 못한 값({result}), 다음 방법 시도")
    except Exception as e:
        print(f"    → BM_GETCHECK 실패: {e}")

    # --- 방법 1: pywinauto UIA ---
    try:
        from pywinauto import Application
        app = Application(backend='uia').connect(handle=login_hwnd)
        win = app.window(handle=login_hwnd)
        chk = win.child_window(handle=mock_chk_hwnd)
        state = chk.get_toggle_state()  # 0=Unchecked, 1=Checked, 2=Indeterminate
        print(f"    → UIA ToggleState: {state}")
        return state == 1
    except Exception as e:
        print(f"    → UIA 방법 실패: {e}")
    
    # --- 방법 2: 체크박스 중앙 픽셀 밝기 ---
    try:
        import pyautogui
        rect = win32gui.GetWindowRect(mock_chk_hwnd)
        cx = (rect[0] + rect[2]) // 2
        cy = (rect[1] + rect[3]) // 2
        # 중앙 3x3 픽셀만 샘플링
        region_size = 3
        shot = pyautogui.screenshot(region=(cx - 1, cy - 1, region_size, region_size))
        raw = shot.tobytes()  # R,G,B bytes
        pixel_values = [b for b in raw]
        avg_brightness = sum(pixel_values) / len(pixel_values)
        # 어두울수록 체크됨 (체크마크 = 어두운색)
        # tobytes() 기준: 체크됨≈148, 해제됨≈240 → 중간값 195 사용
        is_dark = avg_brightness < 195
        print(f"    → 픽셀 밝기(평균): {avg_brightness:.1f} → {'체크됨' if is_dark else '해제됨'}")
        return is_dark
    except Exception as e:
        print(f"    → 픽셀 방법 실패: {e}")
        return None



def login_kiwoom():
    print("=" * 60)
    print("키움증권 자동 로그인을 시작합니다")
    print("=" * 60)
    
    handle_popups()
    
    # 1. 로그인 창 찾기
    login_hwnd = win32gui.FindWindow(None, "Open API Login")
    if not login_hwnd:
        def find_cb(hwnd, _):
            nonlocal login_hwnd
            if not win32gui.IsWindowVisible(hwnd): return
            title = win32gui.GetWindowText(hwnd)
            if "Open API" in title and "Login" in title:
                login_hwnd = hwnd
                return False
        win32gui.EnumWindows(find_cb, None)
    
    if not login_hwnd:
        print("로그인 창을 찾을 수 없습니다.")
        return
    
    # 2. 자식 컨트롤 찾기
    id_edit   = find_child_by_ctrl_id(login_hwnd, CTRL_ID_USERID)
    pw_edit   = find_child_by_ctrl_id(login_hwnd, CTRL_ID_PASSWORD)
    cert_edit = find_child_by_ctrl_id(login_hwnd, CTRL_ID_CERTPW)
    login_btn = find_child_by_ctrl_id(login_hwnd, CTRL_ID_LOGIN_BTN)
    mock_chk  = find_child_by_ctrl_id(login_hwnd, CTRL_ID_MOCK_CHK)
    
    if not id_edit or not pw_edit:
        print("입력 필드를 찾을 수 없습니다.")
        return

    # 3. 모의투자 체크박스 상태 확인 (BM_GETCHECK → UIA → 픽셀 방식)
    if mock_chk:
        print(f"\n[2] 모의투자 체크박스 상태 확인 중...")
        is_checked = is_checkbox_checked(login_hwnd, mock_chk)
        target = config.IS_MOCK_INVESTMENT
        
        if is_checked is None:
            # 판별 불가: 목표 상태에 맞게 강제로 설정 시도
            # 실거래 모드이면 체크 해제가 목표이므로 클릭 후 재확인
            target_str = "체크(모의)" if target else "해제(실거래)"
            print(f"    → 판별 불가. 목표({target_str})를 위해 강제 클릭 시도")
            win32api.SendMessage(mock_chk, BM_CLICK, 0, 0)
            time.sleep(0.5)
            is_checked = is_checkbox_checked(login_hwnd, mock_chk)
            if is_checked is None:
                print(f"    → 재확인도 불가. 현재 상태를 알 수 없어 추가 조작을 건너뜁니다.")
            else:
                state_str = "체크됨(모의)" if is_checked else "해제됨(실거래)"
                print(f"    → 클릭 후 재확인: {state_str}")
                if is_checked != target:
                    print(f"    → 목표와 다름. 한 번 더 클릭합니다.")
                    win32api.SendMessage(mock_chk, BM_CLICK, 0, 0)
                    time.sleep(0.5)
                    final_check = is_checkbox_checked(login_hwnd, mock_chk)
                    print(f"    → 최종 상태: {'체크됨' if final_check else '해제됨'}")
        else:
            state_str = "체크됨(모의)" if is_checked else "해제됨(실거래)"
            target_str = "체크(모의)" if target else "해제(실거래)"
            print(f"    현재: {state_str}, 목표: {target_str}")

            if is_checked != target:
                print(f"    → 클릭하여 변경합니다.")
                win32api.SendMessage(mock_chk, BM_CLICK, 0, 0)
                time.sleep(0.5)
                new_checked = is_checkbox_checked(login_hwnd, mock_chk)
                result_str = '체크됨' if new_checked else ('해제됨' if new_checked is False else '판별불가')
                print(f"    → 변경 후: {result_str}")
                if new_checked != target:
                    print(f"    ⚠️ 경고: 변경 후에도 목표 상태({target_str})에 도달하지 못했습니다!")
            else:
                print(f"    → 이미 올바른 상태입니다.")


    # ── 입력 전 로그인 창을 전경으로 가져오기 ──
    print("[1] 로그인 창 전경 설정...")
    _force_foreground(login_hwnd)

    # 4. ID 입력
    print(f"\n[3] ID 입력 중...")
    send_text_to_control(id_edit, config.USER_ID, login_hwnd)
    time.sleep(0.4)

    # 5. 비밀번호 입력
    print(f"[4] 비밀번호 입력 중...")
    send_text_to_control(pw_edit, config.USER_PW, login_hwnd)
    time.sleep(0.4)

    # 6. 인증비밀번호 (실거래 시)
    if not config.IS_MOCK_INVESTMENT and cert_edit:
        print(f"[5] 인증비밀번호 입력 중...")
        send_text_to_control(cert_edit, config.CERT_PW, login_hwnd)
        time.sleep(0.5)

    time.sleep(0.3)

    # 7. 로그인 버튼 클릭
    print(f"\n[6] 로그인 버튼 클릭!")
    
    # 방법1: BM_CLICK SendMessage (가장 확실)
    print(f"    → BM_CLICK SendMessage")
    win32api.SendMessage(login_btn, BM_CLICK, 0, 0)
    time.sleep(2)
    
    # 창이 남아있으면 방법2: WM_LBUTTONDOWN/UP
    if win32gui.IsWindow(login_hwnd) and win32gui.IsWindowVisible(login_hwnd):
        print(f"    → WM_LBUTTONDOWN/UP")
        send_click_to_control(login_btn)
        time.sleep(2)
    
    # 여전히 창이 있으면 방법3: pyautogui 물리 클릭
    if win32gui.IsWindow(login_hwnd) and win32gui.IsWindowVisible(login_hwnd):
        print(f"    → pyautogui 물리 클릭")
        import pyautogui
        rect = win32gui.GetWindowRect(login_btn)
        cx = (rect[0] + rect[2]) // 2
        cy = (rect[1] + rect[3]) // 2

        # SetForegroundWindow: 서브프로세스에서는 실패할 수 있으므로 방어적으로 처리
        try:
            # keybd_event 트릭: Alt 키를 눌렀다 놓으면 다른 프로세스도 SetForeground 가능
            user32 = ctypes.windll.user32
            user32.keybd_event(0x12, 0, 0, 0)        # Alt down
            user32.keybd_event(0x12, 0, 0x0002, 0)   # Alt up
            time.sleep(0.1)
            win32gui.SetForegroundWindow(login_hwnd)
            print(f"    → SetForegroundWindow 성공")
        except Exception as e:
            print(f"    → SetForegroundWindow 실패({e}), BringWindowToTop 시도")
            try:
                ctypes.windll.user32.ShowWindow(login_hwnd, 9)   # SW_RESTORE
                ctypes.windll.user32.BringWindowToTop(login_hwnd)
            except Exception as e2:
                print(f"    → BringWindowToTop도 실패: {e2} (좌표 클릭만 시도)")

        time.sleep(0.3)
        pyautogui.click(cx, cy)
        time.sleep(2)
    
    time.sleep(3)
    handle_popups()
    print("\n자동 로그인 완료.")




if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "popup":
        handle_popups()
    else:
        login_kiwoom()
