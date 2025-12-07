# Phase 2.5 구현 계획서

> **목표**: Phase 3 진행 전 기존 PDF/PPTX 처리 품질 향상 및 시스템 운영 안정화

**예상 소요 시간**: 1.5-2주
**우선순위**: High
**작성일**: 2025-01-09

---

## 📋 Overview

Phase 2.5는 Excel 지원(Phase 3) 전에 현재 시스템의 품질과 운영성을 개선하는 단계입니다.

### 핵심 목표
1. ✅ **Question Classifier 로깅**: 오분류 케이스 분석 및 개선
2. ✅ **PDF Vision 처리**: 그래프/표 검색 품질 향상
3. ✅ **Exhaustive Retrieval 자동화**: 키워드 의존성 제거
4. ✅ **ChromaDB 동시 접속**: 네트워크 폴더 환경 안정화
5. ✅ **성능 모니터링**: 병목 지점 식별 및 최적화
6. 🔄 **피드백 시스템**: 사용자 만족도 추적 (선택)

---

## 🛠️ Task 1: Question Classifier 로깅 시스템

### 목표
분류기의 동작을 추적하여 오분류 케이스를 식별하고 개선합니다.

### 구현 상세

#### 1.1 로깅 인프라 구축
**파일**: `utils/question_classifier.py`

```python
import logging
import json
from datetime import datetime
from pathlib import Path

# 로그 디렉토리 생성
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 전용 로거 생성
classifier_logger = logging.getLogger("question_classifier")
classifier_logger.setLevel(logging.INFO)
classifier_logger.propagate = False  # 상위 로거로 전파 방지

# 파일 핸들러 (JSONL 형식)
fh = logging.FileHandler(LOG_DIR / "classifier_history.jsonl", encoding="utf-8")
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
fh.setFormatter(formatter)
classifier_logger.addHandler(fh)

# 콘솔 핸들러 (verbose 모드용)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
classifier_logger.addHandler(ch)
```

#### 1.2 분류 로그 기록
**수정**: `classify_question()` 함수

```python
def classify_question(
    query: str,
    use_llm: bool = True,
    verbose: bool = False
) -> dict:
    """
    질문을 분류하고 로그 기록

    Returns:
        {
            "question_type": str,
            "confidence": float,
            "reasoning": str,
            "method": str  # "llm" | "rule"
        }
    """
    start_time = time.time()

    # 기존 분류 로직
    result = _classify_internal(query, use_llm)

    # 로그 엔트리 생성
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "question_type": result["question_type"],
        "confidence": result.get("confidence", 1.0),
        "method": "llm" if use_llm else "rule",
        "reasoning": result.get("reasoning", ""),
        "processing_time_ms": int((time.time() - start_time) * 1000)
    }

    # JSONL 기록
    classifier_logger.info(json.dumps(log_entry, ensure_ascii=False))

    # 콘솔 출력 (verbose 모드)
    if verbose:
        print(f"[Classifier] {query[:50]}... → {result['question_type']} "
              f"(conf: {result.get('confidence', 1.0):.2f})")

    return result
```

#### 1.3 분석 도구 개발
**신규 파일**: `scripts/analyze_classifier_logs.py`

```python
"""
Question Classifier 로그 분석 도구
Usage: python scripts/analyze_classifier_logs.py
"""
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta

def analyze_classifier_logs(log_file: str = "logs/classifier_history.jsonl"):
    """분류기 로그 분석"""

    if not Path(log_file).exists():
        print(f"⚠️  로그 파일 없음: {log_file}")
        return

    # 로그 로드
    logs = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                logs.append(json.loads(line))
            except:
                continue

    if not logs:
        print("📭 로그 데이터 없음")
        return

    print(f"\n{'='*60}")
    print(f"Question Classifier 분석 리포트")
    print(f"{'='*60}")
    print(f"총 쿼리 수: {len(logs)}")
    print(f"분석 기간: {logs[0]['timestamp'][:10]} ~ {logs[-1]['timestamp'][:10]}")

    # 1. 타입별 분포
    print(f"\n[1] 질문 유형 분포")
    type_dist = Counter(log['question_type'] for log in logs)
    for qtype, count in type_dist.most_common():
        pct = count / len(logs) * 100
        print(f"  {qtype:20s}: {count:4d} ({pct:5.1f}%)")

    # 2. 신뢰도 분석
    print(f"\n[2] 신뢰도 분석")
    confidences = [log.get('confidence', 1.0) for log in logs]
    avg_conf = sum(confidences) / len(confidences)
    print(f"  평균 신뢰도: {avg_conf:.3f}")

    low_conf_logs = [log for log in logs if log.get('confidence', 1.0) < 0.7]
    if low_conf_logs:
        pct = len(low_conf_logs) / len(logs) * 100
        print(f"  낮은 신뢰도 (<0.7): {len(low_conf_logs)} ({pct:.1f}%)")

        print(f"\n  [낮은 신뢰도 샘플]")
        for log in low_conf_logs[:5]:
            print(f"    - {log['query'][:50]}...")
            print(f"      → {log['question_type']} (conf: {log['confidence']:.2f})")
    else:
        print(f"  낮은 신뢰도 케이스 없음 ✅")

    # 3. 메소드 분포
    print(f"\n[3] 분류 방법")
    method_dist = Counter(log['method'] for log in logs)
    for method, count in method_dist.most_common():
        pct = count / len(logs) * 100
        print(f"  {method:10s}: {count:4d} ({pct:5.1f}%)")

    # 4. 처리 시간
    print(f"\n[4] 처리 성능")
    times = [log.get('processing_time_ms', 0) for log in logs]
    avg_time = sum(times) / len(times)
    max_time = max(times)
    print(f"  평균 처리 시간: {avg_time:.1f}ms")
    print(f"  최대 처리 시간: {max_time:.1f}ms")

    # 5. 일별 트렌드
    print(f"\n[5] 일별 쿼리 수")
    daily_counts = defaultdict(int)
    for log in logs:
        date = log['timestamp'][:10]
        daily_counts[date] += 1

    for date in sorted(daily_counts.keys())[-7:]:  # 최근 7일
        count = daily_counts[date]
        print(f"  {date}: {count:3d} queries")

    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    analyze_classifier_logs()
```

**예상 소요 시간**: 1일

---

## 🖼️ Task 2: PDF 그래프/표 Vision 처리

### 목표
PDF의 그래프, 표, 도식 이미지를 GPT-4o Vision으로 분석하여 검색 가능하게 만듭니다.

### 구현 상세

#### 2.1 PDF 이미지 추출
**파일**: `utils/pdf_image_extractor.py` (신규)

```python
"""
PDF 이미지 추출 및 Vision 분석
"""
import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image
import io
from typing import List, Dict

def extract_images_from_pdf(pdf_path: str) -> List[Dict]:
    """
    PDF에서 이미지 추출

    Returns:
        [
            {
                "page": int,
                "image_index": int,
                "image_bytes": bytes,
                "width": int,
                "height": int
            },
            ...
        ]
    """
    doc = fitz.open(pdf_path)
    images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images()

        for img_idx, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)

            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            # PIL로 이미지 로드 (크기 확인)
            pil_image = Image.open(io.BytesIO(image_bytes))
            width, height = pil_image.size

            # 너무 작은 이미지 제외 (아이콘, 로고 등)
            if width < 100 or height < 100:
                continue

            # 512x512로 리사이즈 (비용 절감)
            pil_image.thumbnail((512, 512), Image.Resampling.LANCZOS)

            # 다시 바이트로 변환
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            resized_bytes = buffer.getvalue()

            images.append({
                "page": page_num + 1,
                "image_index": img_idx,
                "image_bytes": resized_bytes,
                "width": pil_image.size[0],
                "height": pil_image.size[1],
                "original_ext": image_ext
            })

    doc.close()
    return images
```

#### 2.2 Vision 분석 (GPT-4o)
**파일**: `utils/pdf_image_extractor.py` (계속)

```python
def analyze_image_with_vision(
    image_bytes: bytes,
    llm_vision,  # OpenAI Vision LLM
    page_num: int
) -> str:
    """
    이미지를 GPT-4o Vision으로 분석

    Returns:
        검색 가능한 텍스트 설명
    """
    import base64

    # 이미지를 base64로 인코딩
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    prompt = f"""다음 이미지는 논문의 {page_num}페이지에 있는 그래프, 표, 또는 도식입니다.
이 이미지를 분석하여 검색 가능한 텍스트로 변환하세요.

**출력 형식**:
1. 이미지 타입: [그래프/표/도식/사진]
2. 주요 내용:
   - [핵심 내용을 2-3문장으로 요약]
3. 세부 정보:
   - 축 제목/범례 (그래프인 경우)
   - 열/행 제목 (표인 경우)
   - 주요 수치 데이터
   - 트렌드 또는 패턴

**중요**: 과학 논문 검색을 위한 것이므로, 기술적 용어를 정확히 표기하세요.
"""

    # GPT-4o Vision 호출
    from langchain_core.messages import HumanMessage

    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_base64}"
                }
            }
        ]
    )

    response = llm_vision.invoke([message])
    return response.content
```

#### 2.3 Document Processor 통합
**파일**: `utils/document_processor.py` (수정)

```python
def process_pdf_with_vision(
    self,
    file_path: str,
    enable_vision: bool = False
) -> List[Document]:
    """
    PDF 처리 (텍스트 + Vision 이미지 분석)
    """
    # 기존 텍스트 청킹
    text_docs = self._process_pdf_text(file_path)

    if not enable_vision:
        return text_docs

    # Vision 이미지 분석
    from utils.pdf_image_extractor import extract_images_from_pdf, analyze_image_with_vision

    images = extract_images_from_pdf(file_path)

    if not images:
        return text_docs

    # GPT-4o Vision LLM 초기화
    llm_vision = self._get_vision_llm()

    # 이미지별 분석
    image_docs = []
    for img in images:
        try:
            description = analyze_image_with_vision(
                img["image_bytes"],
                llm_vision,
                img["page"]
            )

            # Document 생성
            doc = Document(
                page_content=f"[페이지 {img['page']} 이미지]\n{description}",
                metadata={
                    "source": file_path,
                    "page": img["page"],
                    "type": "image",
                    "image_index": img["image_index"]
                }
            )
            image_docs.append(doc)

        except Exception as e:
            print(f"⚠️  이미지 분석 실패 (페이지 {img['page']}): {e}")

    # 텍스트 + 이미지 문서 병합
    # 페이지별로 정렬하여 삽입
    all_docs = text_docs + image_docs
    all_docs.sort(key=lambda x: (x.metadata.get("page", 0), x.metadata.get("type", "text")))

    return all_docs
```

#### 2.4 비용 최적화: 오프라인 대안 (Camelot)
**파일**: `utils/pdf_table_extractor.py` (신규, 선택 사항)

```python
"""
오프라인 표 추출 (Camelot 사용)
비용 절감을 위한 대안
"""
import camelot

def extract_tables_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Camelot으로 PDF 표 추출

    Returns:
        [
            {
                "page": int,
                "table_index": int,
                "markdown": str
            },
            ...
        ]
    """
    # Camelot으로 표 추출
    tables = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')

    results = []
    for i, table in enumerate(tables):
        # DataFrame을 Markdown으로 변환
        markdown = table.df.to_markdown(index=False)

        results.append({
            "page": table.page,
            "table_index": i,
            "markdown": f"[표 {i+1}]\n{markdown}"
        })

    return results
```

**비용 비교**:
- **GPT-4o Vision**: 100페이지 × 5 이미지 × $0.00638 (512x512) = **$3.19**
- **Camelot**: 무료 (오프라인)

**예상 소요 시간**: 3-4일

---

## 🔍 Task 3: Exhaustive Retrieval 자동 감지

### 목표
"모든/전체" 키워드 없이도 LLM이 쿼리 복잡도를 판단하여 자동으로 exhaustive retrieval을 트리거합니다.

### 구현 상세

#### 3.1 쿼리 복잡도 분석기
**파일**: `utils/query_analyzer.py` (신규)

```python
"""
쿼리 범위 자동 감지
"""
from typing import Dict

def analyze_query_scope(
    query: str,
    llm,
    temperature: float = 0.0
) -> Dict[str, any]:
    """
    쿼리의 검색 범위를 LLM으로 판단

    Returns:
        {
            "scope": "narrow" | "medium" | "broad",
            "recommended_top_k": int,
            "reason": str
        }
    """

    prompt = f"""다음 질문의 검색 범위를 판단하세요.

질문: {query}

판단 기준:
- **narrow**: 특정 저자/논문/개념에 대한 구체적 질문
  예: "Balkenhol이 2020년에 발표한 논문은?", "OLED 효율 정의는?"
  → 소수의 문서(3-5개)로 답변 가능

- **medium**: 여러 개념 비교, 관계 분석, 특정 주제 요약
  예: "A와 B의 차이점은?", "최근 OLED 연구 동향은?"
  → 중간 규모 문서(10-20개) 필요

- **broad**: 특정 주제에 대한 포괄적 조사, 전체 리뷰
  예: "Balkenhol의 모든 연구 설명", "OLED 관련 모든 논문 요약"
  → 대규모 문서(50-100개) 필요

응답 형식 (JSON만):
{{
    "scope": "narrow|medium|broad",
    "reason": "판단 근거를 1문장으로"
}}
"""

    # LLM 호출
    response = llm.invoke(prompt, temperature=temperature)

    # JSON 파싱
    import json
    import re

    # JSON 블록 추출
    json_match = re.search(r'\{[^}]+\}', response.content, re.DOTALL)
    if not json_match:
        # 파싱 실패 시 기본값
        return {"scope": "narrow", "recommended_top_k": 3, "reason": "파싱 실패"}

    result = json.loads(json_match.group())

    # scope에 따라 top_k 추천
    scope_to_top_k = {
        "narrow": 3,
        "medium": 10,
        "broad": 100
    }

    result["recommended_top_k"] = scope_to_top_k.get(result["scope"], 3)

    return result
```

#### 3.2 RAGChain 통합
**파일**: `utils/rag_chain.py` (수정)

```python
def invoke(self, query: str, **kwargs) -> Dict:
    """
    질문에 답변 (자동 exhaustive retrieval 지원)
    """
    # 1. 쿼리 범위 분석 (옵션)
    if self.enable_auto_exhaustive:
        from utils.query_analyzer import analyze_query_scope

        scope_result = analyze_query_scope(query, self.llm)

        # 로그 기록
        print(f"[Query Scope] {scope_result['scope']} "
              f"(top_k: {scope_result['recommended_top_k']}) "
              f"- {scope_result['reason']}")

        # top_k 동적 조정
        dynamic_top_k = scope_result["recommended_top_k"]
    else:
        dynamic_top_k = self.top_k

    # 2. 기존 검색 로직
    docs = self._search_candidates(query, top_k=dynamic_top_k)

    # ... (이하 동일)
```

**예상 소요 시간**: 2-3일

---

## 🔐 Task 4: ChromaDB 동시 접속 대응

### 목표
네트워크 폴더 환경에서 여러 사용자가 동시에 DB를 사용할 때 파일 잠금 오류를 방지합니다.

### 구현 상세

#### 4.1 읽기 전용 모드
**파일**: `utils/vector_store.py` (수정)

```python
class VectorStoreManager:
    def __init__(
        self,
        ...,
        mode: str = "readwrite"  # "readonly" | "readwrite"
    ):
        """
        Args:
            mode:
                - "readonly": 읽기 전용 (공유 DB용)
                - "readwrite": 읽기/쓰기 가능 (개인 DB용)
        """
        self.mode = mode

        if mode == "readonly":
            # 읽기 전용 클라이언트
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    allow_reset=False,
                    anonymized_telemetry=False
                )
            )
        else:
            # 읽기/쓰기 클라이언트
            self.client = chromadb.PersistentClient(
                path=persist_directory
            )

    def add_documents(self, docs: List[Document]):
        """문서 추가 (읽기 전용 모드에서는 오류)"""
        if self.mode == "readonly":
            raise PermissionError(
                "공유 DB는 읽기 전용입니다. 개인 DB에 추가하세요."
            )

        # ... 기존 로직
```

#### 4.2 파일 잠금 처리
**파일**: `utils/db_lock.py` (신규)

```python
"""
DB 파일 잠금 관리
네트워크 환경에서 쓰기 충돌 방지
"""
import time
from pathlib import Path
from datetime import datetime

class DBLock:
    """
    간단한 파일 기반 잠금
    """
    def __init__(self, db_path: str):
        self.lock_file = Path(db_path) / ".lock"
        self.lock_info_file = Path(db_path) / ".lock_info"

    def acquire(self, timeout: int = 10) -> bool:
        """
        잠금 획득

        Args:
            timeout: 대기 시간 (초)

        Returns:
            True if success, False if timeout
        """
        start = time.time()

        while self.lock_file.exists():
            # 타임아웃 체크
            if time.time() - start > timeout:
                # 잠금 정보 읽기
                if self.lock_info_file.exists():
                    with open(self.lock_info_file, 'r') as f:
                        lock_info = f.read()
                    raise TimeoutError(
                        f"DB 잠금 획득 실패 (타임아웃)\n"
                        f"다른 사용자가 DB를 사용 중입니다: {lock_info}"
                    )
                else:
                    raise TimeoutError("DB 잠금 획득 실패 (타임아웃)")

            time.sleep(0.5)

        # 잠금 파일 생성
        self.lock_file.touch()

        # 잠금 정보 기록
        with open(self.lock_info_file, 'w') as f:
            f.write(f"User: {os.getenv('USERNAME', 'unknown')}\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write(f"PID: {os.getpid()}\n")

        return True

    def release(self):
        """잠금 해제"""
        if self.lock_file.exists():
            self.lock_file.unlink()
        if self.lock_info_file.exists():
            self.lock_info_file.unlink()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
```

#### 4.3 사용 예시
**파일**: `utils/vector_store.py` (수정)

```python
def add_documents(self, docs: List[Document]):
    """문서 추가 (파일 잠금 사용)"""
    if self.mode == "readonly":
        raise PermissionError("읽기 전용 모드에서는 추가 불가")

    from utils.db_lock import DBLock

    # 잠금 획득 후 추가
    with DBLock(self.persist_directory):
        # ... 기존 add_documents 로직
        pass
```

**예상 소요 시간**: 1-2일

---

## 📊 Task 5: 성능 모니터링 시스템

### 목표
각 단계별 처리 시간을 측정하여 병목 지점을 식별합니다.

### 구현 상세

#### 5.1 성능 로거
**파일**: `utils/performance_logger.py` (신규)

```python
"""
성능 측정 및 로깅
"""
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

# 로그 디렉토리
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 성능 로거
perf_logger = logging.getLogger("performance")
perf_logger.setLevel(logging.INFO)
perf_logger.propagate = False

fh = logging.FileHandler(LOG_DIR / "performance_history.jsonl", encoding="utf-8")
formatter = logging.Formatter('%(message)s')
fh.setFormatter(formatter)
perf_logger.addHandler(fh)

class PerformanceTracker:
    """
    성능 측정 컨텍스트 매니저
    """
    def __init__(self, query: str):
        self.query = query
        self.start_time = None
        self.breakdown = {}

    @contextmanager
    def measure(self, step_name: str):
        """단계별 시간 측정"""
        step_start = time.time()
        try:
            yield
        finally:
            elapsed_ms = int((time.time() - step_start) * 1000)
            self.breakdown[f"{step_name}_ms"] = elapsed_ms

    def start(self):
        """전체 측정 시작"""
        self.start_time = time.time()

    def finish(self, **extra_info):
        """측정 완료 및 로그 기록"""
        total_time_ms = int((time.time() - self.start_time) * 1000)

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": self.query,
            "total_time_ms": total_time_ms,
            "breakdown": self.breakdown,
            **extra_info
        }

        # 로그 기록
        perf_logger.info(json.dumps(log_entry, ensure_ascii=False))

        # 병목 경고 (3초 이상)
        if total_time_ms > 3000:
            print(f"⚠️  느린 쿼리 감지 ({total_time_ms}ms): {self.query[:50]}...")

            # 가장 느린 단계 식별
            slowest_step = max(self.breakdown.items(), key=lambda x: x[1])
            print(f"    병목: {slowest_step[0]} ({slowest_step[1]}ms)")

        return log_entry
```

#### 5.2 RAGChain 통합
**파일**: `utils/rag_chain.py` (수정)

```python
def invoke(self, query: str, **kwargs) -> Dict:
    """질문에 답변 (성능 측정)"""

    from utils.performance_logger import PerformanceTracker

    tracker = PerformanceTracker(query)
    tracker.start()

    # 1. 검색
    with tracker.measure("retrieval"):
        docs = self._search_candidates(query)

    # 2. Re-ranking
    with tracker.measure("reranking"):
        if self.use_reranker:
            docs = self._rerank_documents(query, docs)

    # 3. 컨텍스트 확장
    with tracker.measure("context_expansion"):
        expanded_docs = self._expand_context(docs)

    # 4. LLM 생성
    with tracker.measure("llm_generation"):
        answer = self._generate_answer(query, expanded_docs)

    # 측정 완료
    perf_info = tracker.finish(
        llm_model=self.llm_model,
        num_docs_retrieved=len(docs),
        final_docs=len(expanded_docs)
    )

    return {
        "answer": answer,
        "sources": expanded_docs,
        "performance": perf_info
    }
```

#### 5.3 분석 도구
**파일**: `scripts/analyze_performance_logs.py` (신규)

```python
"""
성능 로그 분석
"""
import json
from pathlib import Path
from collections import defaultdict
import statistics

def analyze_performance(log_file: str = "logs/performance_history.jsonl"):
    """성능 로그 분석"""

    logs = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            logs.append(json.loads(line))

    print(f"\n{'='*60}")
    print(f"성능 분석 리포트")
    print(f"{'='*60}")
    print(f"총 쿼리 수: {len(logs)}")

    # 1. 전체 응답 시간
    total_times = [log['total_time_ms'] for log in logs]
    print(f"\n[1] 전체 응답 시간")
    print(f"  평균: {statistics.mean(total_times):.1f}ms")
    print(f"  중앙값: {statistics.median(total_times):.1f}ms")
    print(f"  최대: {max(total_times):.1f}ms")
    print(f"  최소: {min(total_times):.1f}ms")

    # 2. 단계별 평균 시간
    print(f"\n[2] 단계별 평균 시간")
    steps = defaultdict(list)
    for log in logs:
        for step, time_ms in log['breakdown'].items():
            steps[step].append(time_ms)

    for step, times in sorted(steps.items(), key=lambda x: -statistics.mean(x[1])):
        avg_time = statistics.mean(times)
        pct = avg_time / statistics.mean(total_times) * 100
        print(f"  {step:25s}: {avg_time:6.1f}ms ({pct:4.1f}%)")

    # 3. 느린 쿼리 (상위 5개)
    print(f"\n[3] 느린 쿼리 Top 5")
    slow_queries = sorted(logs, key=lambda x: x['total_time_ms'], reverse=True)[:5]
    for i, log in enumerate(slow_queries, 1):
        print(f"  {i}. {log['query'][:50]}...")
        print(f"     시간: {log['total_time_ms']}ms")

        # 병목 단계
        slowest_step = max(log['breakdown'].items(), key=lambda x: x[1])
        print(f"     병목: {slowest_step[0]} ({slowest_step[1]}ms)")

if __name__ == "__main__":
    analyze_performance()
```

**예상 소요 시간**: 1일

---

## 👍 Task 6: 사용자 피드백 시스템 (선택)

### 목표
답변 품질에 대한 사용자 피드백을 수집하여 시스템 개선에 활용합니다.

### 구현 상세

#### 6.1 UI 수정
**파일**: `ui/chat_widget.py` (수정)

```python
class ChatWidget(QWidget):
    def _add_assistant_message(self, message: str, sources: List[Dict]):
        """
        어시스턴트 메시지 추가 (피드백 버튼 포함)
        """
        # 기존 메시지 표시
        msg_widget = QWidget()
        layout = QVBoxLayout(msg_widget)

        # 메시지 텍스트
        text_label = QLabel(message)
        layout.addWidget(text_label)

        # 피드백 버튼
        feedback_layout = QHBoxLayout()

        thumbs_up = QPushButton("👍 도움됨")
        thumbs_up.clicked.connect(
            lambda: self._record_feedback("positive", message, sources)
        )

        thumbs_down = QPushButton("👎 개선 필요")
        thumbs_down.clicked.connect(
            lambda: self._record_feedback("negative", message, sources)
        )

        feedback_layout.addWidget(thumbs_up)
        feedback_layout.addWidget(thumbs_down)
        feedback_layout.addStretch()

        layout.addLayout(feedback_layout)

        self.chat_area.addWidget(msg_widget)

    def _record_feedback(
        self,
        rating: str,
        answer: str,
        sources: List[Dict]
    ):
        """피드백 기록"""
        from utils.feedback_logger import log_feedback

        # 사용자 코멘트 입력 (선택)
        comment, ok = QInputDialog.getText(
            self,
            "피드백",
            "추가 의견이 있으면 입력하세요 (선택):"
        )

        if ok:
            log_feedback(
                query=self.current_query,
                answer=answer,
                rating=rating,
                user_comment=comment if comment else "",
                sources_used=[s.get("source", "") for s in sources]
            )

            QMessageBox.information(self, "감사합니다", "피드백이 기록되었습니다.")
```

#### 6.2 피드백 로거
**파일**: `utils/feedback_logger.py` (신규)

```python
"""
사용자 피드백 로깅
"""
import json
import logging
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

feedback_logger = logging.getLogger("user_feedback")
feedback_logger.setLevel(logging.INFO)
feedback_logger.propagate = False

fh = logging.FileHandler(LOG_DIR / "user_feedback.jsonl", encoding="utf-8")
formatter = logging.Formatter('%(message)s')
fh.setFormatter(formatter)
feedback_logger.addHandler(fh)

def log_feedback(
    query: str,
    answer: str,
    rating: str,  # "positive" | "negative"
    user_comment: str = "",
    sources_used: List[str] = None
):
    """피드백 기록"""

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "answer": answer,
        "rating": rating,
        "user_comment": user_comment,
        "sources_used": sources_used or []
    }

    feedback_logger.info(json.dumps(log_entry, ensure_ascii=False))

    # 부정 피드백 알림
    if rating == "negative":
        print(f"⚠️  부정 피드백: {query[:50]}...")
```

#### 6.3 주간 리포트
**파일**: `scripts/generate_weekly_feedback_report.py` (신규)

```python
"""
주간 피드백 리포트 생성
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

def generate_weekly_report(log_file: str = "logs/user_feedback.jsonl"):
    """주간 피드백 리포트"""

    # 최근 7일 로그만
    cutoff = datetime.now() - timedelta(days=7)

    logs = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            log = json.loads(line)
            log_time = datetime.fromisoformat(log['timestamp'])
            if log_time >= cutoff:
                logs.append(log)

    print(f"\n{'='*60}")
    print(f"주간 피드백 리포트")
    print(f"{'='*60}")
    print(f"기간: {cutoff.date()} ~ {datetime.now().date()}")
    print(f"총 피드백 수: {len(logs)}")

    # 1. 만족도
    ratings = Counter(log['rating'] for log in logs)
    print(f"\n[1] 사용자 만족도")
    for rating, count in ratings.most_common():
        pct = count / len(logs) * 100
        emoji = "😊" if rating == "positive" else "😞"
        print(f"  {emoji} {rating:10s}: {count:3d} ({pct:5.1f}%)")

    # 2. 부정 피드백 케이스
    negative_logs = [log for log in logs if log['rating'] == 'negative']
    if negative_logs:
        print(f"\n[2] 개선 필요 케이스 ({len(negative_logs)}건)")
        for log in negative_logs[:5]:
            print(f"\n  질문: {log['query']}")
            print(f"  답변: {log['answer'][:100]}...")
            if log['user_comment']:
                print(f"  의견: {log['user_comment']}")

    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    generate_weekly_report()
```

**예상 소요 시간**: 2일 (선택 사항)

---

## 📅 Phase 2.5 완료 체크리스트

### 필수 작업
- [ ] Task 1: Question Classifier 로깅 구현 및 1주일 데이터 수집
- [ ] Task 2: PDF Vision 처리 구현 및 10개 논문 테스트
- [ ] Task 3: Exhaustive Retrieval 자동 감지 구현 및 정확도 80% 검증
- [ ] Task 4: ChromaDB 동시 접속 대응 및 3명 이상 테스트
- [ ] Task 5: 성능 모니터링 구현 및 1주일 데이터 수집

### 선택 작업
- [ ] Task 6: 사용자 피드백 시스템 구현

### 성능 목표
- [ ] 평균 응답 시간 5초 이하 (Llama-4-scout 기준)
- [ ] Re-ranking 처리 시간 1.5초 이하 (60개 문서)
- [ ] 메모리 사용량 2GB 이하

### 품질 목표
- [ ] Question Classifier 평균 신뢰도 0.8 이상
- [ ] PDF Vision 분석 정확도 90% 이상 (수동 검증)
- [ ] Exhaustive Retrieval 자동 감지 정확도 80% 이상

---

**작성자**: Claude Code
**최종 업데이트**: 2025-01-09
