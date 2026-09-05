import os
import logging
from datetime import datetime

class StrategyManager:
    """파일 기반 전략 관리자"""
    
    def __init__(self, base_dir=None):
        if base_dir is None:
            # 현재 파일의 상위 디렉토리 기준
            base_dir = os.path.dirname(os.path.dirname(__file__))
        self.strategy_dir = os.path.join(base_dir, 'strategy')
        self._ensure_strategy_folder()
    
    def _ensure_strategy_folder(self):
        """strategy 폴더가 없으면 생성"""
        if not os.path.exists(self.strategy_dir):
            os.makedirs(self.strategy_dir)
            logging.info(f"Created strategy directory: {self.strategy_dir}")
    
    def save_strategy(self, name, content):
        """전략을 strategy 폴더에 .txt 파일로 저장"""
        try:
            file_path = os.path.join(self.strategy_dir, f"{name}.txt")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logging.info(f"Strategy '{name}' saved to {file_path}")
            return True
        except Exception as e:
            logging.error(f"Error saving strategy {name}: {str(e)}")
            return False
    
    def get_strategies(self):
        """strategy 폴더의 모든 전략 파일 목록 반환 (하위 디렉토리 포함)"""
        try:
            strategies = []
            
            if os.path.exists(self.strategy_dir):
                for root, dirs, files in os.walk(self.strategy_dir):
                    for filename in files:
                        if filename.endswith('.txt'):
                            # 상대 경로를 포함한 이름 생성 (예: 'dual/DUAL_ETFS_SPREAD')
                            rel_path = os.path.relpath(os.path.join(root, filename), self.strategy_dir)
                            name = rel_path[:-4].replace('\\', '/') # .txt 제거 및 경로 구분자 통일
                            
                            file_path = os.path.join(root, filename)
                            
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # 타입 추출 (INI 스타일 [INFO] 또는 [설정] 섹션 확인)
                            import configparser
                            import io
                            strat_type = 'single' # 기본값
                            try:
                                config = configparser.ConfigParser()
                                config.read_string(content)
                                if config.has_section('INFO') and config.has_option('INFO', 'type'):
                                    strat_type = config.get('INFO', 'type')
                                elif config.has_section('설정') and config.has_option('설정', 'type'):
                                    strat_type = config.get('설정', 'type')
                                elif '/' in name:
                                    strat_type = 'dual'
                            except:
                                if '/' in name: strat_type = 'dual'
                            
                            # 파일 수정 시간
                            mtime = os.path.getmtime(file_path)
                            updated_at = datetime.fromtimestamp(mtime)
                            
                            strategies.append({
                                'name': name,
                                'content': content,
                                'type': strat_type,
                                'updated_at': updated_at
                            })
            
            # 최신순 정렬
            strategies.sort(key=lambda x: x['updated_at'], reverse=True)
            return strategies
        except Exception as e:
            logging.error(f"Error fetching strategies: {str(e)}")
            return []
    
    def get_strategy(self, name):
        """특정 전략 파일 읽기 (경로가 불완전해도 검색 시도)"""
        try:
            # 1. 직접 경로 시도
            normalized_name = name.replace('/', os.sep).replace('\\', os.sep)
            file_path = os.path.join(self.strategy_dir, f"{normalized_name}.txt")
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {'name': name, 'content': content}
            
            # 2. 파일명으로 검색 시도 (경로 없이 이름만 들어온 경우 등)
            filename_to_find = os.path.basename(normalized_name) + ".txt"
            logging.info(f"[StrategyManager] Direct path failed. Searching for {filename_to_find} in {self.strategy_dir}")
            
            for root, dirs, files in os.walk(self.strategy_dir):
                if filename_to_find in files:
                    found_path = os.path.join(root, filename_to_find)
                    logging.info(f"[StrategyManager] Found strategy at: {found_path}")
                    with open(found_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return {'name': name, 'content': content}
                    
            logging.warning(f"Strategy file not found: {name}")
            return None
        except Exception as e:
            logging.error(f"Error fetching strategy {name}: {str(e)}")
            return None
    
    def delete_strategy(self, name):
        """전략 파일 삭제"""
        try:
            file_path = os.path.join(self.strategy_dir, f"{name}.txt")
            
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Strategy '{name}' deleted from {file_path}")
                return True
            else:
                logging.warning(f"Strategy file not found for deletion: {file_path}")
                return False
        except Exception as e:
            logging.error(f"Error deleting strategy {name}: {str(e)}")
            return False
