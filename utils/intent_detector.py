"""
Intent Detector
사용자 질문에서 특정 문서 참조 의도 감지

업로드 직후 "이 문서에서...", "방금 올린 파일..." 같은 패턴 감지
"""
import re
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class IntentDetector:
    """문서 참조 의도 감지

    사용자 질문에서 특정 문서를 참조하는 패턴을 감지하여
    해당 문서 우선 검색을 가능하게 함

    Examples:
        >>> detector = IntentDetector()
        >>> result = detector.detect_document_reference("이 문서에서 뭐라고 했어?")
        >>> print(result['has_reference'])  # True
        >>> print(result['confidence'])  # 0.9

        >>> result = detector.detect_document_reference("report.pdf에서 결론 부분 찾아줘")
        >>> print(result['mentioned_filename'])  # "report.pdf"
    """

    def __init__(self):
        """IntentDetector 초기화"""

        # 문서 참조 패턴 (한국어)
        self.ko_reference_patterns = [
            # 지시대명사 기반
            r"(이|그|저)\s*(문서|파일|PDF|논문|보고서|자료)",

            # 시간 기반 참조
            r"(방금|지금|금방|조금\s*전|아까|직전에)\s*(올린|업로드한|첨부한|추가한|보낸)",
            r"(최근에?|recently)\s*(올린|업로드한|첨부한|추가한)",

            # 동작 기반
            r"(올린|업로드한|첨부한|추가한|보낸)\s*(문서|파일|PDF|논문|보고서|자료)",
            r"(내가|제가)\s*(올린|업로드한|첨부한|추가한|보낸)",

            # 직접 언급
            r"(위|윗)\s*(문서|파일|PDF)",
            r"(해당|관련)\s*(문서|파일|PDF)",
        ]

        # 문서 참조 패턴 (영어)
        self.en_reference_patterns = [
            r"(this|that|the)\s*(document|file|PDF|paper|report)",
            r"(uploaded|attached|added)\s*(document|file|PDF)",
            r"(just|recently)\s*(uploaded|attached|added)",
            r"(I|i)\s*(uploaded|attached|added)",
        ]

        # 파일명 추출 패턴 (우선순위 순서)
        self.filename_patterns = [
            # 1. 따옴표로 감싼 파일명 (최우선): "논문.pdf", '보고서.docx'
            r"[\"']([^\"']+\.(?:pdf|docx?|xlsx?|pptx?|txt|hwp))[\"']",

            # 2. @멘션 스타일: @파일명.pdf
            r"@([가-힣a-zA-Z0-9_\-\s]+\.(?:pdf|docx?|xlsx?|pptx?|txt|hwp))",

            # 3. 단어 경계로 구분된 파일명 (공백/문장부호 전후)
            # group(1): 전체 파일명.확장자
            r"(?:^|[\s])([가-힣a-zA-Z0-9_\-]+(?:\s+[가-힣a-zA-Z0-9_\-]+)*\.(?:pdf|docx?|xlsx?|pptx?|txt|hwp))(?:[\s]|$|에서|을|를|와|과|,|\.)",
        ]

        # 컴파일된 패턴 저장
        self.compiled_ko_patterns = [re.compile(p, re.IGNORECASE) for p in self.ko_reference_patterns]
        self.compiled_en_patterns = [re.compile(p, re.IGNORECASE) for p in self.en_reference_patterns]
        self.compiled_filename_patterns = [re.compile(p, re.IGNORECASE) for p in self.filename_patterns]

        logger.info("IntentDetector 초기화 완료")

    def detect_document_reference(self, question: str) -> Dict:
        """문서 참조 의도 감지

        Args:
            question: 사용자 질문

        Returns:
            {
                'has_reference': bool,  # 문서 참조 여부
                'confidence': float,    # 신뢰도 (0.0 ~ 1.0)
                'matched_patterns': List[str],  # 매칭된 패턴들
                'mentioned_filename': Optional[str]  # 언급된 파일명
            }
        """
        matched_patterns = []
        confidence = 0.0
        mentioned_filename = None

        # 1. 파일명 명시적 언급 확인 (최우선)
        mentioned_filename = self._extract_filename(question)
        if mentioned_filename:
            matched_patterns.append(f"filename:{mentioned_filename}")
            confidence = 1.0  # 파일명 명시는 100% 확신

            logger.debug(f"파일명 명시 감지: {mentioned_filename}")

            return {
                'has_reference': True,
                'confidence': confidence,
                'matched_patterns': matched_patterns,
                'mentioned_filename': mentioned_filename
            }

        # 2. 한국어 참조 패턴 확인
        ko_matches = self._match_patterns(question, self.compiled_ko_patterns, self.ko_reference_patterns)
        matched_patterns.extend(ko_matches)

        # 3. 영어 참조 패턴 확인
        en_matches = self._match_patterns(question, self.compiled_en_patterns, self.en_reference_patterns)
        matched_patterns.extend(en_matches)

        # 신뢰도 계산
        if matched_patterns:
            # 패턴 개수에 따라 신뢰도 증가 (최대 0.95)
            base_confidence = 0.7
            pattern_bonus = min(len(matched_patterns) * 0.1, 0.25)
            confidence = min(base_confidence + pattern_bonus, 0.95)

            logger.debug(f"문서 참조 감지: {len(matched_patterns)}개 패턴 매칭, 신뢰도={confidence:.2f}")

        return {
            'has_reference': len(matched_patterns) > 0,
            'confidence': confidence,
            'matched_patterns': matched_patterns,
            'mentioned_filename': None
        }

    def _extract_filename(self, text: str) -> Optional[str]:
        """텍스트에서 파일명 추출

        Args:
            text: 검색할 텍스트

        Returns:
            추출된 파일명 (없으면 None)
        """
        for pattern in self.compiled_filename_patterns:
            match = pattern.search(text)
            if match:
                # 모든 패턴에서 group(1)이 파일명
                filename = match.group(1)
                filename = filename.strip().strip('"\'@')  # 따옴표, @ 제거

                # 공백 정규화
                filename = ' '.join(filename.split())

                return filename

        return None

    def _match_patterns(self, text: str, compiled_patterns: List, original_patterns: List[str]) -> List[str]:
        """패턴 매칭 수행

        Args:
            text: 검색할 텍스트
            compiled_patterns: 컴파일된 정규식 패턴 리스트
            original_patterns: 원본 패턴 문자열 리스트 (로깅용)

        Returns:
            매칭된 원본 패턴 문자열 리스트
        """
        matches = []

        for i, pattern in enumerate(compiled_patterns):
            if pattern.search(text):
                matches.append(original_patterns[i])

        return matches

    def extract_all_filenames(self, text: str) -> List[str]:
        """텍스트에서 모든 파일명 추출 (여러 파일 언급 시)

        Args:
            text: 검색할 텍스트

        Returns:
            추출된 파일명 리스트
        """
        filenames = []

        for pattern in self.compiled_filename_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                # 모든 패턴에서 group(1)이 파일명
                filename = match.group(1)
                filename = filename.strip().strip('"\'@')
                filename = ' '.join(filename.split())

                if filename and filename not in filenames:
                    filenames.append(filename)

        return filenames

    def get_reference_strength(self, question: str) -> float:
        """문서 참조 강도 측정 (간편 메서드)

        Args:
            question: 사용자 질문

        Returns:
            참조 강도 (0.0 ~ 1.0)
        """
        result = self.detect_document_reference(question)
        return result['confidence']

    def has_strong_reference(self, question: str, threshold: float = 0.7) -> bool:
        """강한 문서 참조 여부 판단

        Args:
            question: 사용자 질문
            threshold: 신뢰도 임계값 (기본 0.7)

        Returns:
            True if 신뢰도 >= threshold
        """
        result = self.detect_document_reference(question)
        return result['has_reference'] and result['confidence'] >= threshold

    def __repr__(self):
        return (f"IntentDetector("
                f"ko_patterns={len(self.ko_reference_patterns)}, "
                f"en_patterns={len(self.en_reference_patterns)})")


# 편의 함수
def detect_intent(question: str) -> Dict:
    """전역 IntentDetector를 사용한 간편 감지 함수

    Args:
        question: 사용자 질문

    Returns:
        detect_document_reference() 결과
    """
    detector = IntentDetector()
    return detector.detect_document_reference(question)
