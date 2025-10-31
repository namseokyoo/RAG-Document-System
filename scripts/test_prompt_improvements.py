"""
프롬프트 엔지니어링 개선 및 Phase 2 검증 테스트
"""
import os
import sys
from typing import List, Dict, Any

# ensure project root on sys.path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
import json
from datetime import datetime


def print_header(title: str):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def test_prompt_improvements():
    """프롬프트 개선 및 Phase 2 검증 테스트"""
    print_header("프롬프트 엔지니어링 개선 및 Phase 2 검증 테스트")
    
    cfg = ConfigManager()
    conf = cfg.get_all()
    
    # 1. 벡터스토어 초기화
    print("\n[1/4] 벡터스토어 초기화")
    vector_store = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=conf.get("embedding_api_type"),
        embedding_base_url=conf.get("embedding_base_url"),
        embedding_model=conf.get("embedding_model"),
        embedding_api_key=conf.get("embedding_api_key", "")
    )
    
    # 2. RAG 체인 초기화
    print("\n[2/4] RAG 체인 초기화")
    rag_chain = RAGChain(
        vectorstore=vector_store.vectorstore,
        llm_api_type=conf.get("llm_api_type"),
        llm_base_url=conf.get("llm_base_url"),
        llm_model=conf.get("llm_model"),
        llm_api_key=conf.get("llm_api_key", ""),
        temperature=conf.get("temperature", 0.3),
        top_k=conf.get("top_k", 12),
        use_reranker=conf.get("use_reranker", True),
        reranker_model=conf.get("reranker_model", "multilingual-base"),
        reranker_initial_k=conf.get("reranker_initial_k", 120),
        enable_synonym_expansion=conf.get("enable_synonym_expansion", True),
        enable_multi_query=conf.get("enable_multi_query", True)
    )
    
    # 3. 테스트 질문
    print_header("[3/4] 테스트 질문 실행")
    
    test_questions = [
        "논문에서 사용한 TADF 재료는 무엇인가?",
        "ACRSA의 성능 지표는?",
        "실험 결과를 요약해줘",
        "TADF 재료와 HF 성능의 관계는?",
    ]
    
    results = []
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*80}")
        print(f"질문 #{i}: {question}")
        print(f"{'='*80}")
        
        try:
            # 답변 생성
            result = rag_chain.query(question, chat_history=[])
            
            answer = result.get("answer", "")
            confidence = result.get("confidence", 0.0)
            sources = result.get("sources", [])
            
            print(f"\n답변:")
            print(f"{answer}")
            print(f"\n신뢰도: {confidence:.1f}%")
            print(f"출처: {len(sources)}개")
            
            # 답변 품질 분석 (검증 결과는 이미 query() 내부에서 수행됨)
            verification = None
                
            results.append({
                "question": question,
                "answer": answer,
                "confidence": confidence,
                "num_sources": len(sources),
                "verification": verification
            })
            
        except Exception as e:
            print(f"❌ 오류: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "question": question,
                "answer": f"오류: {str(e)}",
                "confidence": 0.0,
                "num_sources": 0,
                "verification": None
            })
    
    # 4. 결과 요약
    print_header("[4/4] 결과 요약")
    
    total_questions = len(results)
    valid_answers = sum(1 for r in results if r.get("verification") and r.get("verification", {}).get("is_valid", False))
    avg_confidence = sum(r.get("confidence", 0) for r in results) / total_questions if total_questions > 0 else 0
    
    print(f"\n전체 질문 수: {total_questions}")
    if total_questions > 0:
        print(f"검증 통과 답변: {valid_answers}/{total_questions} ({valid_answers/total_questions*100:.1f}%)")
    print(f"평균 신뢰도: {avg_confidence:.1f}%")
    
    # 세부 통계
    verifications = [r["verification"] for r in results if r.get("verification")]
    if verifications:
        avg_total_score = sum(v.get("total_score", 0) for v in verifications) / len(verifications)
        print(f"평균 검증 점수: {avg_total_score:.2f}")
    
    # 재생성 통계
    regenerated_count = sum(1 for r in results if "재생성" in str(r.get("answer", "")))
    print(f"재생성된 답변: {regenerated_count}개 (검증 실패 시)")
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"test_reports/prompt_improvement_test_{timestamp}.json"
    os.makedirs("test_reports", exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "total_questions": total_questions,
            "valid_answers": valid_answers,
            "avg_confidence": avg_confidence,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 테스트 결과 저장: {output_file}")
    
    return results


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 100)
    print("프롬프트 엔지니어링 개선 및 Phase 2 검증 테스트")
    print("=" * 100)
    
    try:
        results = test_prompt_improvements()
        
        print("\n" + "=" * 100)
        print("테스트 완료!")
        print("=" * 100)
        
        return 0
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

