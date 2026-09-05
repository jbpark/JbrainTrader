"""
키움증권 로그인 창의 모든 자식 컨트롤을 분석합니다.
로그인 창이 떠 있는 상태에서 실행하세요.
"""
import win32gui
import win32con
import ctypes

print("=" * 60)
print("키움증권 로그인 창 자식 컨트롤 분석")
print("=" * 60)

# 로그인 창 찾기
def find_login_window():
    results = []
    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd): return
        title = win32gui.GetWindowText(hwnd)
        if "Open API" in title or "키움" in title or "로그인" in title:
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            results.append((hwnd, title, w, h, rect))
    win32gui.EnumWindows(cb, None)
    return results

wins = find_login_window()
if not wins:
    print("로그인 창을 찾을 수 없습니다. 로그인 창을 띄워놓고 다시 실행하세요.")
    input("Press Enter to exit...")
    exit()

print(f"\n발견된 창 ({len(wins)}개):")
for hwnd, title, w, h, rect in wins:
    print(f"  hwnd={hwnd}, title=[{title}], size={w}x{h}, rect={rect}")

# 가장 큰 창을 메인 로그인 창으로 선택
main = max(wins, key=lambda x: x[2] * x[3])
main_hwnd = main[0]
main_rect = main[4]
print(f"\n메인 로그인 창: hwnd={main_hwnd}, title=[{main[1]}], size={main[2]}x{main[3]}")
print(f"  rect: left={main_rect[0]}, top={main_rect[1]}, right={main_rect[2]}, bottom={main_rect[3]}")

# 모든 자식 컨트롤 열거
print(f"\n{'='*60}")
print(f"자식 컨트롤 목록:")
print(f"{'='*60}")

children = []
def enum_child(child_hwnd, _):
    cls = win32gui.GetClassName(child_hwnd)
    text = win32gui.GetWindowText(child_hwnd)
    rect = win32gui.GetWindowRect(child_hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    # 부모 창 기준 상대 좌표
    rel_x = rect[0] - main_rect[0]
    rel_y = rect[1] - main_rect[1]
    style = win32gui.GetWindowLong(child_hwnd, win32con.GWL_STYLE)
    ctrl_id = win32gui.GetDlgCtrlID(child_hwnd)
    visible = bool(style & win32con.WS_VISIBLE)
    is_password = bool(style & 0x20)  # ES_PASSWORD = 0x20
    
    children.append({
        'hwnd': child_hwnd,
        'cls': cls,
        'text': text,
        'rel_x': rel_x,
        'rel_y': rel_y,
        'w': w,
        'h': h,
        'ctrl_id': ctrl_id,
        'visible': visible,
        'is_password': is_password,
        'style': hex(style),
    })

try:
    win32gui.EnumChildWindows(main_hwnd, enum_child, None)
except:
    pass

for i, c in enumerate(children):
    pw_flag = " [*** PASSWORD ***]" if c['is_password'] else ""
    vis_flag = "V" if c['visible'] else "H"
    print(f"  [{i:2d}] hwnd={c['hwnd']:8d} cls={c['cls']:20s} "
          f"id={c['ctrl_id']:5d} [{vis_flag}] "
          f"pos=({c['rel_x']:3d},{c['rel_y']:3d}) size={c['w']:3d}x{c['h']:2d} "
          f"style={c['style']} text=[{c['text']}]{pw_flag}")

# Edit 컨트롤 요약
print(f"\n{'='*60}")
print(f"Edit 컨트롤 요약:")
print(f"{'='*60}")
edits = [c for c in children if 'Edit' in c['cls'] or c['is_password']]
for c in edits:
    pw = "PASSWORD" if c['is_password'] else "TEXT"
    print(f"  hwnd={c['hwnd']}, type={pw}, pos=({c['rel_x']},{c['rel_y']}), "
          f"size={c['w']}x{c['h']}, ctrl_id={c['ctrl_id']}, text=[{c['text']}]")

# Button 컨트롤 요약
print(f"\n{'='*60}")
print(f"Button 컨트롤 요약:")
print(f"{'='*60}")
buttons = [c for c in children if c['cls'] == 'Button']
for c in buttons:
    print(f"  hwnd={c['hwnd']}, pos=({c['rel_x']},{c['rel_y']}), "
          f"size={c['w']}x{c['h']}, ctrl_id={c['ctrl_id']}, text=[{c['text']}]")

print(f"\n완료. 총 {len(children)}개 자식 컨트롤")
input("Press Enter to exit...")
