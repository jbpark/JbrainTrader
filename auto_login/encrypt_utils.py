from cryptography.fernet import Fernet
import os
import getpass

def generate_key():
    """키를 생성하고 파일로 저장합니다."""
    key = Fernet.generate_key()
    with open("secret.key", "wb") as key_file:
        key_file.write(key)
    print("secret.key 파일이 생성되었습니다. 이 파일을 분실하지 않도록 주의하세요.")

def load_key():
    """저장된 키를 불러옵니다."""
    return open("secret.key", "rb").read()

def encrypt_data():
    if not os.path.exists("secret.key"):
        generate_key()
    
    key = load_key()
    f = Fernet(key)
    
    print("--- 키움증권 계정 정보 암호화 도구 ---")
    user_id = input("아이디(USER_ID): ").encode()
    user_pw = getpass.getpass("비밀번호(USER_PW): ").encode()
    cert_pw = getpass.getpass("인증비밀번호(CERT_PW, 없으면 엔터): ").encode()
    
    enc_id = f.encrypt(user_id).decode()
    enc_pw = f.encrypt(user_pw).decode()
    enc_cert = f.encrypt(cert_pw).decode()
    
    # .env 파일 업데이트 (또는 생성)
    env_content = f"""KIWOOM_USER_ID={enc_id}
KIWOOM_USER_PW={enc_pw}
KIWOOM_CERT_PW={enc_cert}
KIWOOM_IS_MOCK=1
"""
    with open(".env", "w", encoding="utf-8") as env_file:
        env_file.write(env_content)
    
    print("\n.env 파일에 암호화된 정보가 저장되었습니다.")

if __name__ == "__main__":
    encrypt_data()
