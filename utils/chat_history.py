import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional


class ChatHistoryManager:
    def __init__(self, history_dir: str = "chat_history"):
        self.history_dir = history_dir
        os.makedirs(history_dir, exist_ok=True)
    
    def get_history_file(self, session_id: str) -> str:
        """세션 ID에 대한 히스토리 파일 경로 반환"""
        return os.path.join(self.history_dir, f"{session_id}.json")
    
    def load_history(self, session_id: str) -> List[Dict[str, Any]]:
        """세션의 대화 이력 로드"""
        history_file = self.get_history_file(session_id)
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"이력 로드 실패: {e}")
                return []
        return []
    
    def save_message(self, session_id: str, question: str, answer: str, 
                     sources: List[Dict[str, Any]] = None):
        """대화 메시지 저장"""
        history = self.load_history(session_id)
        
        message = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer,
            "sources": sources or []
        }
        
        history.append(message)
        
        history_file = self.get_history_file(session_id)
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"이력 저장 실패: {e}")
            return False
    
    def clear_history(self, session_id: str) -> bool:
        """세션의 대화 이력 삭제"""
        history_file = self.get_history_file(session_id)
        try:
            if os.path.exists(history_file):
                os.remove(history_file)
            return True
        except Exception as e:
            print(f"이력 삭제 실패: {e}")
            return False
    
    def get_all_sessions(self) -> List[str]:
        """모든 세션 ID 목록 반환"""
        try:
            files = os.listdir(self.history_dir)
            return [f.replace('.json', '') for f in files if f.endswith('.json')]
        except Exception as e:
            print(f"세션 목록 조회 실패: {e}")
            return []
    
    def export_history(self, session_id: str, export_path: str) -> bool:
        """대화 이력을 다른 파일로 내보내기"""
        history = self.load_history(session_id)
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"이력 내보내기 실패: {e}")
            return False
    
    def get_all_sessions_with_info(self) -> List[Dict[str, Any]]:
        """모든 세션의 정보 반환 (제목, 시간, 메시지 수 등)"""
        sessions = []
        try:
            session_ids = self.get_all_sessions()
            
            for session_id in session_ids:
                history = self.load_history(session_id)
                if not history:
                    continue
                
                # 첫 메시지 정보
                first_message = history[0]
                first_question = first_message.get("question", "")
                timestamp = first_message.get("timestamp", "")
                
                # 세션 제목 생성: YYMMDD_[첫 질문 10글자]
                title = self._generate_session_title(timestamp, first_question)
                
                sessions.append({
                    "session_id": session_id,
                    "title": title,
                    "timestamp": timestamp,
                    "message_count": len(history),
                    "first_question": first_question
                })
            
            # 최신 순으로 정렬
            sessions.sort(key=lambda x: x["timestamp"], reverse=True)
            return sessions
            
        except Exception as e:
            print(f"세션 정보 조회 실패: {e}")
            return []
    
    def _generate_session_title(self, timestamp: str, first_question: str) -> str:
        """세션 제목 생성: YYMMDD_[첫 질문 10글자]"""
        try:
            # timestamp에서 날짜 추출 (ISO 형식: 2025-10-18T...)
            date_part = timestamp[:10].replace("-", "")[2:]  # YYMMDD
            
            # 첫 질문 10글자 (공백 제거)
            question_part = first_question.replace(" ", "")[:10]
            
            return f"{date_part}_{question_part}"
        except Exception as e:
            print(f"제목 생성 실패: {e}")
            return "세션"

