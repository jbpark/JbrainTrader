import os
from pathlib import Path
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# 이 파일(config.py)의 위치를 기준으로 상위 폴더(.env, secret.key 위치)를 찾음
_BASE_DIR = Path(__file__).parent.parent  # auto_login_001\ 폴더

# .env 파일 로드
load_dotenv(dotenv_path=_BASE_DIR / ".env")

_KEY_PATH = _BASE_DIR / "secret.key"

def get_decrypted_value(key_name, default_value):
    encrypted_value = os.getenv(key_name)
    if not encrypted_value or encrypted_value == default_value:
        return default_value
    
    try:
        if not _KEY_PATH.exists():
            return default_value
        
        with open(_KEY_PATH, "rb") as key_file:
            key = key_file.read()
            f = Fernet(key)
            return f.decrypt(encrypted_value.encode()).decode()
    except Exception as e:
        print(f"복호화 오류 ({key_name}): {e}")
        return default_value

USER_ID = get_decrypted_value("KIWOOM_USER_ID", "YOUR_ID")
USER_PW = get_decrypted_value("KIWOOM_USER_PW", "YOUR_PASSWORD")
CERT_PW = get_decrypted_value("KIWOOM_CERT_PW", "YOUR_CERT_PASSWORD")
ACC_PW  = get_decrypted_value("KIWOOM_ACC_PW", USER_PW) # 기본값은 USER_PW로 설정

# 모의투자 여부 (True: 모의투자, False: 실거래)
IS_MOCK_INVESTMENT = os.getenv("KIWOOM_IS_MOCK", "1") == "1"

