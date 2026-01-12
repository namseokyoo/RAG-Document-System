"""
질문 분류기 정확도 테스트 스크립트

100개 테스트 케이스로 분류 정확도를 검증합니다.
결과를 파일로 저장하고 보고서를 생성합니다.
"""

import sys
import os
import io
from datetime import datetime

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 출력 파일 경로
OUTPUT_DIR = "logs/test"
os.makedirs(OUTPUT_DIR, exist_ok=True)
REPORT_FILE = os.path.join(OUTPUT_DIR, f"question_classifier_accuracy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

from utils.question_classifier import create_classifier
from utils.vector_store import VectorStoreManager
import json

def load_config():
    """설정 파일 로드"""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # 기본 설정 반환
        return {
            "llm_api_type": "request",
            "llm_base_url": "http://localhost:11434",
            "llm_model": "gemma3:latest",
            "embedding_api_type": "ollama",
            "embedding_base_url": "http://localhost:11434",
            "embedding_model": "mxbai-embed-large",
            "chroma_distance_function": "cosine",
            "shared_db_path": None,
            "shared_db_enabled": False
        }

# 테스트 데이터셋
TEST_DATASET = [
    # --- 1. simple_fact (단순 사실) ---
    {"question": "mCBP의 삼중항 에너지(T1) 값은 얼마야?", "expected": "simple_fact"},
    {"question": "DPEPO의 녹는점(Tm) 알려줘.", "expected": "simple_fact"},
    {"question": "Ir(ppy)3의 분자량이 몇이지?", "expected": "simple_fact"},
    {"question": "이 논문의 3페이지 요약해줘.", "expected": "simple_fact"},
    {"question": "가장 높은 EQE 수치는 몇 %야?", "expected": "simple_fact"},
    {"question": "Figure 4 그래프의 X축 단위가 뭐야?", "expected": "simple_fact"},
    {"question": "T-1 호스트 재료의 HOMO 레벨 값은?", "expected": "simple_fact"},
    {"question": "실험체 A-1의 증착 속도는 얼마였어?", "expected": "simple_fact"},
    {"question": "특허 US10234567의 출원일은?", "expected": "simple_fact"},
    {"question": "Blue Dopant B-2의 최대 파장(PL max) 값 알려줘.", "expected": "simple_fact"},
    
    # --- 2. simple_keyword (키워드 검색) ---
    {"question": "Changmin Keum 교수가 쓴 논문 찾아줘.", "expected": "simple_keyword"},
    {"question": "파일명에 'OLED'가 들어가는 파일 검색해.", "expected": "simple_keyword"},
    {"question": "2024년에 작성된 보고서만 보여줘.", "expected": "simple_keyword"},
    {"question": "삼성디스플레이(SDC) 관련 문헌 검색해줘.", "expected": "simple_keyword"},
    {"question": "'Lifetime' 키워드가 포함된 슬라이드 찾아.", "expected": "simple_keyword"},
    {"question": "저자가 'Adachi'인 논문 리스트 검색.", "expected": "simple_keyword"},
    {"question": "프로젝트 코드 'PJ-102' 관련 문서 찾아줘.", "expected": "simple_keyword"},
    {"question": "'Degradation' 단어가 들어가는 페이지 검색.", "expected": "simple_keyword"},
    {"question": "김연구 수석이 작성한 파일 찾아줘.", "expected": "simple_keyword"},
    {"question": "키워드 'Inkjet'으로 검색해봐.", "expected": "simple_keyword"},
    
    # --- 3. normal_definition (정의) ---
    {"question": "TADF가 정확히 무슨 뜻이야?", "expected": "normal_definition"},
    {"question": "EQE(외부양자효율)의 정의가 뭐야?", "expected": "normal_definition"},
    {"question": "OLED에서 'Roll-off' 현상이란?", "expected": "normal_definition"},
    {"question": "Polaron이 뭔지 설명해줘.", "expected": "normal_definition"},
    {"question": "Dexter Energy Transfer의 개념이 궁금해.", "expected": "normal_definition"},
    {"question": "역계간교차(RISC)란 무엇인가?", "expected": "normal_definition"},
    {"question": "엑시플렉스(Exciplex) 형성이라는 게 무슨 말이야?", "expected": "normal_definition"},
    {"question": "정공 수송층(HTL)의 역할이 뭐야?", "expected": "normal_definition"},
    {"question": "Outcoupling efficiency의 뜻은?", "expected": "normal_definition"},
    {"question": "도판트(Dopant)가 뭔지 정의해줘.", "expected": "normal_definition"},
    
    # --- 4. normal_explanation (설명/이유) ---
    {"question": "청색 OLED의 수명이 짧은 원인이 뭐야?", "expected": "normal_explanation"},
    {"question": "TADF 소자는 어떤 원리로 발광해?", "expected": "normal_explanation"},
    {"question": "왜 고휘도에서 효율이 급격히 떨어지는지 설명해줘.", "expected": "normal_explanation"},
    {"question": "용액 공정이 증착 공정보다 어려운 이유는?", "expected": "normal_explanation"},
    {"question": "OLED 패널의 번인(Burn-in)은 왜 생기는 거야?", "expected": "normal_explanation"},
    {"question": "호스트와 도판트의 에너지 레벨이 왜 맞아야 해?", "expected": "normal_explanation"},
    {"question": "전자 수송층 두께를 늘리면 어떤 현상이 발생해?", "expected": "normal_explanation"},
    {"question": "수평 배향이 광추출 효율을 높이는 원리 설명해.", "expected": "normal_explanation"},
    {"question": "TTA(Triplet-Triplet Annihilation) 메커니즘 설명해줘.", "expected": "normal_explanation"},
    {"question": "초형광(Hyperfluorescence) 기술이 왜 주목받는 거야?", "expected": "normal_explanation"},
    
    # --- 5. normal_translation_direct (직접 번역 - 검색 Skip) ---
    {"question": "이 문단을 영어로 번역해줘.", "expected": "normal_translation_direct"},
    {"question": "Translate the following abstract into Korean.", "expected": "normal_translation_direct"},
    {"question": "방금 복사한 내용을 한글로 바꿔줄래?", "expected": "normal_translation_direct"},
    {"question": "위의 실험 결과를 영어로 작문해줘.", "expected": "normal_translation_direct"},
    {"question": "이 문장을 학술적인 영어 표현으로 고쳐서 번역해줘.", "expected": "normal_translation_direct"},
    {"question": "Change this paragraph to English.", "expected": "normal_translation_direct"},
    {"question": "다음 텍스트를 한국어로 번역.", "expected": "normal_translation_direct"},
    {"question": "이 일본어 특허 문구의 의미를 번역해줘.", "expected": "normal_translation_direct"},
    {"question": "아래 내용을 보고서 말투로 번역해.", "expected": "normal_translation_direct"},
    {"question": "이 부분을 OLED 용어를 써서 영작해줘.", "expected": "normal_translation_direct"},
    
    # --- 6. normal_translation_search (검색 후 번역) ---
    {"question": "DPEPO의 열적 특성에 대한 내용을 찾아서 번역해줘.", "expected": "normal_translation_search"},
    {"question": "최근 청색 소자 수명 이슈 문서를 검색해서 한글로 번역해.", "expected": "normal_translation_search"},
    {"question": "Search for 'TADF definition' and translate it to Korean.", "expected": "normal_translation_search"},
    {"question": "삼성디스플레이 최신 특허 내용을 찾아서 요약 번역해줘.", "expected": "normal_translation_search"},
    {"question": "증착 공정 가이드라인을 검색한 뒤 영어로 바꿔줘.", "expected": "normal_translation_search"},
    {"question": "Find the conclusion of this paper and translate it.", "expected": "normal_translation_search"},
    {"question": "T-1 호스트 재료 물성표를 찾아서 한국어로 번역해줘.", "expected": "normal_translation_search"},
    {"question": "해외 기술 동향 보고서를 검색해서 핵심만 번역해.", "expected": "normal_translation_search"},
    {"question": "이 주제와 관련된 영문 논문 초록을 찾아서 번역해줘.", "expected": "normal_translation_search"},
    {"question": "EQE 측정 매뉴얼을 찾아서 영작해줘.", "expected": "normal_translation_search"},
    
    # --- 7. complex_comparison (비교/분석) ---
    {"question": "형광과 인광의 차이점을 비교해줘.", "expected": "complex_comparison"},
    {"question": "OLED와 QLED의 발광 원리 차이는?", "expected": "complex_comparison"},
    {"question": "진공 증착과 잉크젯 프린팅 방식의 장단점 비교해.", "expected": "complex_comparison"},
    {"question": "TADF 재료와 일반 형광 재료의 수명 특성 비교.", "expected": "complex_comparison"},
    {"question": "상부 발광(Top)과 하부 발광(Bottom) 구조의 차이는?", "expected": "complex_comparison"},
    {"question": "mCBP와 DPEPO를 호스트로 썼을 때 효율 차이 비교해줘.", "expected": "complex_comparison"},
    {"question": "1세대, 2세대, 3세대 발광 재료 특징 비교.", "expected": "complex_comparison"},
    {"question": "단일 호스트와 혼합 호스트(Co-host)의 성능 비교해줘.", "expected": "complex_comparison"},
    {"question": "Glass 기판과 Plastic 기판 사용 시 차이점은?", "expected": "complex_comparison"},
    {"question": "청색 소자와 적색 소자의 열화 메커니즘 차이 비교.", "expected": "complex_comparison"},
    
    # --- 8. complex_relationship (관계/인과) ---
    {"question": "도판트 농도가 발광 효율에 미치는 영향은?", "expected": "complex_relationship"},
    {"question": "동작 온도가 올라가면 수명은 어떻게 변해?", "expected": "complex_relationship"},
    {"question": "박막 두께와 시야각 특성의 상관관계 알려줘.", "expected": "complex_relationship"},
    {"question": "HOMO 에너지 레벨 차이가 구동 전압에 주는 영향은?", "expected": "complex_relationship"},
    {"question": "재료 순도가 소자 수명과 어떤 관계가 있어?", "expected": "complex_relationship"},
    {"question": "전류 밀도가 증가할 때 휘도는 어떻게 변해?", "expected": "complex_relationship"},
    {"question": "T1 에너지 레벨이 RISC 속도에 미치는 영향 설명해줘.", "expected": "complex_relationship"},
    {"question": "기판 굴절률이 광추출 효율에 주는 영향은?", "expected": "complex_relationship"},
    {"question": "발광층 위치에 따른 재결합 영역(RZ)의 변화 관계.", "expected": "complex_relationship"},
    {"question": "쌍극자 모멘트와 배향성의 관계 설명해줘.", "expected": "complex_relationship"},
    
    # --- 9. exhaustive_keyword (전수 조사 - 키워드) ---
    {"question": "데이터베이스에 있는 'Boron' 관련 모든 문서를 찾아줘.", "expected": "exhaustive_keyword"},
    {"question": "이번 프로젝트 폴더에서 '실험' 단어가 든 파일 전부 검색해.", "expected": "exhaustive_keyword"},
    {"question": "OLED 수명 향상에 관한 모든 논문을 찾아줘.", "expected": "exhaustive_keyword"},
    {"question": "최근 3년간의 '청색 소자' 관련 모든 보고서 검색.", "expected": "exhaustive_keyword"},
    {"question": "시스템에 저장된 특허 중 'Samsung'이 출원한 거 싹 다 찾아.", "expected": "exhaustive_keyword"},
    {"question": "'Degradation' 키워드가 포함된 모든 텍스트 가져와.", "expected": "exhaustive_keyword"},
    {"question": "DB 내의 모든 TADF 관련 자료 전수 조사해줘.", "expected": "exhaustive_keyword"},
    {"question": "파일명에 'Meeting'이 들어가는 모든 회의록 찾아.", "expected": "exhaustive_keyword"},
    {"question": "언급된 모든 화학 구조식 이미지 찾아줘.", "expected": "exhaustive_keyword"},
    {"question": "저자가 'Y.K. Kook'인 모든 문헌 검색해줘.", "expected": "exhaustive_keyword"},
    
    # --- 10. exhaustive_list (전수 조사 - 리스트) ---
    {"question": "이번 주 실험 보고서들의 제목 목록만 나열해줘.", "expected": "exhaustive_list"},
    {"question": "저장된 모든 PDF 파일의 리스트를 보여줘.", "expected": "exhaustive_list"},
    {"question": "이 문서에 포함된 모든 그림(Figure)의 캡션 목록 뽑아줘.", "expected": "exhaustive_list"},
    {"question": "참고 문헌(Reference) 리스트 전체 보여줘.", "expected": "exhaustive_list"},
    {"question": "데이터베이스에 있는 저자 이름들 목록으로 만들어줘.", "expected": "exhaustive_list"},
    {"question": "모든 슬라이드의 목차(Index)를 나열해.", "expected": "exhaustive_list"},
    {"question": "검색된 문서들의 날짜별 목록을 줘.", "expected": "exhaustive_list"},
    {"question": "사용 가능한 모든 호스트 재료의 이름 리스트업 해줘.", "expected": "exhaustive_list"},
    {"question": "이 폴더 하위의 모든 파일 경로 목록.", "expected": "exhaustive_list"},
    {"question": "보고서 내의 모든 표(Table) 제목 리스트.", "expected": "exhaustive_list"},
]


def test_classifier_accuracy():
    """질문 분류기 정확도 테스트"""
    # 출력 파일 열기
    output_file = open(REPORT_FILE, 'w', encoding='utf-8')
    
    def log_print(*args, **kwargs):
        """콘솔과 파일에 동시 출력"""
        print(*args, **kwargs)
        print(*args, **kwargs, file=output_file)
    
    log_print("=" * 80)
    log_print("질문 분류기 정확도 테스트")
    log_print("=" * 80)
    log_print(f"테스트 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_print(f"총 테스트 케이스: {len(TEST_DATASET)}개")
    log_print(f"보고서 파일: {REPORT_FILE}\n")
    
    # 설정 로드
    config = load_config()
    
    # VectorStoreManager 초기화 (임베딩 모델 필요)
    log_print("[초기화] VectorStoreManager 초기화 중...")
    vectorstore = VectorStoreManager(
        persist_directory=config.get("chroma_persist_directory", "data/chroma_db"),
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large"),
        embedding_api_key=config.get("embedding_api_key", ""),
        shared_db_path=config.get("shared_db_path"),
        shared_db_enabled=config.get("shared_db_enabled", False),
        distance_function=config.get("chroma_distance_function", "cosine")
    )
    log_print("[초기화] VectorStoreManager 초기화 완료\n")
    
    # LLM 초기화 (계층적 라우팅용)
    log_print("[초기화] LLM 초기화 중...")
    from utils.rag_chain import RAGChain
    rag_chain = RAGChain(
        vectorstore=vectorstore,
        llm_api_type=config.get("llm_api_type", "request"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:latest"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.3)
    )
    llm = rag_chain.llm
    log_print("[초기화] LLM 초기화 완료\n")
    
    # QuestionClassifier 초기화
    log_print("[초기화] QuestionClassifier 초기화 중...")
    classifier = create_classifier(
        llm=llm,
        use_llm=True,
        verbose=False,
        llm_timeout=10.0,
        embeddings=vectorstore.embeddings
    )
    log_print("[초기화] QuestionClassifier 초기화 완료\n")
    
    # 테스트 실행
    log_print("=" * 80)
    log_print("테스트 실행 중...")
    log_print("=" * 80)
    
    results = []
    category_stats = {}  # 카테고리별 통계
    
    for idx, test_case in enumerate(TEST_DATASET, 1):
        question = test_case["question"]
        expected = test_case["expected"]
        
        try:
            # 분류 수행
            result = classifier.classify(question)
            predicted = result.get("detailed_type") or result.get("type")
            method = result.get("method", "unknown")
            confidence = result.get("confidence", 0.0)
            
            # 기본 유형으로 매핑 (detailed_type이 없을 경우)
            if not result.get("detailed_type"):
                base_type = result.get("type", "unknown")
                # 기본 유형을 세부 유형으로 추정
                if base_type == "simple":
                    predicted = "simple_fact"  # 기본값
                elif base_type == "normal":
                    predicted = "normal_explanation"  # 기본값
                elif base_type == "complex":
                    predicted = "complex_relationship"  # 기본값
                elif base_type == "exhaustive":
                    predicted = "exhaustive_list"  # 기본값
                else:
                    predicted = base_type
            
            is_correct = (predicted == expected)
            
            results.append({
                "idx": idx,
                "question": question,
                "expected": expected,
                "predicted": predicted,
                "is_correct": is_correct,
                "method": method,
                "confidence": confidence
            })
            
            # 카테고리별 통계
            if expected not in category_stats:
                category_stats[expected] = {"total": 0, "correct": 0, "wrong": []}
            category_stats[expected]["total"] += 1
            if is_correct:
                category_stats[expected]["correct"] += 1
            else:
                category_stats[expected]["wrong"].append({
                    "question": question,
                    "predicted": predicted,
                    "confidence": confidence
                })
            
            # 진행 상황 출력
            status = "[OK]" if is_correct else "[X]"
            log_print(f"[{idx:3d}/{len(TEST_DATASET)}] {status} {expected:30s} -> {predicted:30s} ({method}, conf={confidence:.2f})")
            if not is_correct:
                log_print(f"         질문: {question[:60]}...")
        
        except Exception as e:
            log_print(f"[{idx:3d}/{len(TEST_DATASET)}] [ERROR] 오류 발생: {e}")
            results.append({
                "idx": idx,
                "question": question,
                "expected": expected,
                "predicted": "ERROR",
                "is_correct": False,
                "method": "error",
                "confidence": 0.0
            })
    
    # 결과 요약
    log_print("\n" + "=" * 80)
    log_print("테스트 결과 요약")
    log_print("=" * 80)
    
    total = len(results)
    correct = sum(1 for r in results if r["is_correct"])
    accuracy = (correct / total * 100) if total > 0 else 0
    
    log_print(f"\n전체 정확도: {correct}/{total} ({accuracy:.2f}%)")
    
    # 카테고리별 정확도
    log_print("\n카테고리별 정확도:")
    log_print("-" * 80)
    for category, stats in sorted(category_stats.items()):
        cat_accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        log_print(f"  {category:30s} {stats['correct']:2d}/{stats['total']:2d} ({cat_accuracy:5.1f}%)")
        if stats["wrong"]:
            log_print(f"    오분류 사례:")
            for wrong_case in stats["wrong"][:3]:  # 최대 3개만 표시
                log_print(f"      - 예상: {category}, 실제: {wrong_case['predicted']} (conf={wrong_case['confidence']:.2f})")
                log_print(f"        질문: {wrong_case['question'][:70]}...")
    
    # 오분류 상세
    wrong_cases = [r for r in results if not r["is_correct"]]
    if wrong_cases:
        log_print(f"\n오분류 상세 ({len(wrong_cases)}개):")
        log_print("-" * 80)
        for case in wrong_cases:
            log_print(f"  [{case['idx']:3d}] 예상: {case['expected']:30s} -> 실제: {case['predicted']:30s}")
            log_print(f"       질문: {case['question']}")
            log_print(f"       방법: {case['method']}, 신뢰도: {case['confidence']:.2f}\n")
    
    # 분류 방법별 통계
    method_stats = {}
    for r in results:
        method = r["method"]
        if method not in method_stats:
            method_stats[method] = {"total": 0, "correct": 0}
        method_stats[method]["total"] += 1
        if r["is_correct"]:
            method_stats[method]["correct"] += 1
    
    log_print("\n분류 방법별 통계:")
    log_print("-" * 80)
    for method, stats in sorted(method_stats.items()):
        method_accuracy = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        log_print(f"  {method:25s} {stats['correct']:2d}/{stats['total']:2d} ({method_accuracy:5.1f}%)")
    
    # 통계 출력
    log_print("\n분류기 통계:")
    log_print("-" * 80)
    total_q = classifier.stats["total"]
    llm_success = classifier.stats.get("llm_success", 0)
    llm_failed = classifier.stats.get("llm_failed", 0)
    rule_only = classifier.stats.get("rule_only", 0)
    semantic_router = classifier.stats.get("semantic_router", 0)
    translation_fasttrack = classifier.stats.get("translation_fasttrack", 0)
    
    log_print(f"  총 질문 수: {total_q}")
    log_print(f"  LLM 성공: {llm_success} ({llm_success/total_q*100:.1f}%)")
    log_print(f"  LLM 실패: {llm_failed} ({llm_failed/total_q*100:.1f}%)")
    log_print(f"  규칙만 사용: {rule_only} ({rule_only/total_q*100:.1f}%)")
    log_print(f"  Semantic Router: {semantic_router} ({semantic_router/total_q*100:.1f}%)")
    log_print(f"  번역 Fast-Track: {translation_fasttrack} ({translation_fasttrack/total_q*100:.1f}%)")
    
    # 상세 결과 테이블
    log_print("\n" + "=" * 80)
    log_print("상세 결과 테이블")
    log_print("=" * 80)
    log_print(f"{'번호':<6} {'예상':<30} {'실제':<30} {'정확':<6} {'방법':<20} {'신뢰도':<8} {'질문':<50}")
    log_print("-" * 80)
    for r in results:
        correct_str = "O" if r["is_correct"] else "X"
        log_print(f"{r['idx']:<6} {r['expected']:<30} {r['predicted']:<30} {correct_str:<6} {r['method']:<20} {r['confidence']:<8.2f} {r['question'][:50]:<50}")
    
    log_print("\n" + "=" * 80)
    log_print("테스트 완료")
    log_print("=" * 80)
    log_print(f"보고서 저장 완료: {REPORT_FILE}")
    
    output_file.close()
    
    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "category_stats": category_stats,
        "method_stats": method_stats,
        "report_file": REPORT_FILE
    }


if __name__ == "__main__":
    result = test_classifier_accuracy()
    print(f"\n테스트 완료! 보고서 파일: {result['report_file']}")
    print(f"전체 정확도: {result['accuracy']:.2f}%")

