"""
현재 화면에 보이는 모든 창과 자식 버튼을 출력합니다.
'업그레이드 확인' 창이 떠 있는 상태에서 이 스크립트를 실행하세요.
"""
import win32gui
import win32con

print("=" * 60)
print("현재 화면에 존재하는 창 목록")
print("=" * 60)

def enum_child_callback(child_hwnd, results):
    cls = win32gui.GetClassName(child_hwnd)
    text = win32gui.GetWindowText(child_hwnd)
    if text or cls:
        results.append(f"      [자식] hwnd={child_hwnd}, cls={cls}, text=[{text}]")

def enum_windows_callback(hwnd, _):
    if not win32gui.IsWindowVisible(hwnd):
        return
    title = win32gui.GetWindowText(hwnd)
    if not title:
        return
    cls = win32gui.GetClassName(hwnd)
    rect = win32gui.GetWindowRect(hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    print(f"hwnd={hwnd}, cls={cls}, title=[{title}], size={w}x{h}")
    
    # 자식 컨트롤 출력
    children = []
    try:
        win32gui.EnumChildWindows(hwnd, enum_child_callback, children)
    except:
        pass
    for c in children:
        print(c)

win32gui.EnumWindows(enum_windows_callback, None)

print("\n")
print("=" * 60)
print("'업그레이드' 키워드로 검색")
print("=" * 60)

def find_upgrade_popup(hwnd, _):
    if not win32gui.IsWindowVisible(hwnd):
        return
    title = win32gui.GetWindowText(hwnd)
    if "업그레이드" in title or "upgrade" in title.lower():
        cls = win32gui.GetClassName(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        print(f">>> 발견! hwnd={hwnd}, cls={cls}, title=[{title}], rect={rect}")
        children = []
        try:
            win32gui.EnumChildWindows(hwnd, enum_child_callback, children)
        except:
            pass
        for c in children:
            print(c)

win32gui.EnumWindows(find_upgrade_popup, None)
print("완료.")
