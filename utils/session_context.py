"""
Session Context Manager
세션 기반 문서 컨텍스트 관리

사용자가 최근 업로드한 문서를 추적하여
업로드 직후 질문 시 해당 문서 우선 검색
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class UploadedDocument:
    """업로드된 문서 정보"""
    document_id: str
    file_name: str
    upload_timestamp: datetime
    num_chunks: int

    def __repr__(self):
        elapsed = (datetime.now() - self.upload_timestamp).total_seconds()
        return f"UploadedDocument(file={self.file_name}, chunks={self.num_chunks}, elapsed={elapsed:.0f}s)"


class SessionContext:
    """세션 기반 문서 컨텍스트 관리

    사용자가 최근 업로드한 문서를 추적하고,
    타임아웃 이내 질문 시 해당 문서를 우선 검색

    Examples:
        >>> session = SessionContext(timeout_seconds=300)  # 5분
        >>> session.add_upload("doc123", "paper.pdf", 21)
        >>>
        >>> # 5분 이내 질문
        >>> if session.is_active():
        >>>     docs = session.get_active_documents()
        >>>     print(f"최근 업로드: {[d.file_name for d in docs]}")
        >>>
        >>> # 타임아웃 경과 후
        >>> session.is_active()  # False
    """

    def __init__(self, timeout_seconds: int = 300):
        """
        Args:
            timeout_seconds: 세션 타임아웃 (기본 5분)
        """
        self.timeout = timedelta(seconds=timeout_seconds)
        self.timeout_seconds = timeout_seconds
        self.recent_uploads: List[UploadedDocument] = []

        logger.info(f"SessionContext 초기화 (timeout={timeout_seconds}초)")

    def add_upload(self, document_id: str, file_name: str, num_chunks: int):
        """문서 업로드 기록

        Args:
            document_id: 문서 고유 ID (UUID)
            file_name: 파일명 (확장자 포함)
            num_chunks: 생성된 청크 개수
        """
        doc = UploadedDocument(
            document_id=document_id,
            file_name=file_name,
            upload_timestamp=datetime.now(),
            num_chunks=num_chunks
        )
        self.recent_uploads.append(doc)

        logger.info(f"📎 Session: 문서 추가 - {file_name} ({num_chunks} chunks)")

        # 오래된 항목 정리 (메모리 절약)
        self._cleanup_old_uploads()

    def get_active_documents(self) -> List[UploadedDocument]:
        """활성 세션 내 문서 반환

        Returns:
            타임아웃 이내 업로드된 문서 리스트 (최신순)
        """
        now = datetime.now()
        active = [
            doc for doc in self.recent_uploads
            if (now - doc.upload_timestamp) < self.timeout
        ]
        return active

    def get_active_document_ids(self) -> List[str]:
        """활성 문서 ID 리스트 반환

        Returns:
            타임아웃 이내 문서 ID 리스트
        """
        return [doc.document_id for doc in self.get_active_documents()]

    def get_active_file_names(self) -> List[str]:
        """활성 파일명 리스트 반환

        Returns:
            타임아웃 이내 파일명 리스트
        """
        return [doc.file_name for doc in self.get_active_documents()]

    def get_most_recent_document(self) -> Optional[UploadedDocument]:
        """가장 최근 업로드 문서 반환

        Returns:
            최근 문서 (없으면 None)
        """
        active = self.get_active_documents()
        return active[-1] if active else None

    def clear(self):
        """세션 초기화 (모든 기록 삭제)"""
        logger.info(f"Session 초기화: {len(self.recent_uploads)}개 기록 삭제")
        self.recent_uploads.clear()

    def is_active(self) -> bool:
        """활성 세션 여부

        Returns:
            True if 타임아웃 이내 업로드 문서 있음
        """
        return len(self.get_active_documents()) > 0

    def get_session_info(self) -> Dict:
        """세션 정보 반환 (디버깅/UI용)

        Returns:
            {
                'active': bool,
                'num_active_docs': int,
                'active_files': List[str],
                'timeout_seconds': int,
                'most_recent': Optional[str]
            }
        """
        active_docs = self.get_active_documents()
        most_recent = self.get_most_recent_document()

        return {
            'active': self.is_active(),
            'num_active_docs': len(active_docs),
            'active_files': [d.file_name for d in active_docs],
            'timeout_seconds': self.timeout_seconds,
            'most_recent': most_recent.file_name if most_recent else None,
            'most_recent_elapsed': (
                (datetime.now() - most_recent.upload_timestamp).total_seconds()
                if most_recent else None
            )
        }

    def _cleanup_old_uploads(self):
        """타임아웃 경과 문서 제거

        타임아웃의 2배 이상 경과한 문서는 메모리에서 제거
        """
        now = datetime.now()
        before_count = len(self.recent_uploads)

        self.recent_uploads = [
            doc for doc in self.recent_uploads
            if (now - doc.upload_timestamp) < self.timeout * 2  # 2배 여유
        ]

        removed = before_count - len(self.recent_uploads)
        if removed > 0:
            logger.debug(f"Session 정리: {removed}개 오래된 기록 제거")

    def __repr__(self):
        active = self.get_active_documents()
        return f"SessionContext(active={len(active)}, timeout={self.timeout_seconds}s)"
