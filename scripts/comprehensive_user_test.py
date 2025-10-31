"""
실사용자 종합 테스트: 다양한 질문 생성 및 검증
"""
import os
import sys
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

# ensure project root on sys.path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
from utils.document_processor import DocumentProcessor
import json


def print_header(title: str):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def generate_questions_with_llm(rag_chain: RAGChain, doc_summaries: List[str], num_questions: int = 15) -> List[str]:
    """LLM을 사용하여 문서 기반 질문 자동 생성"""
    try:
        print(f"\n[LLM 질문 생성] {num_questions}개 질문 생성 중...")
        
        # 문서 요약 정보
        docs_info = "\n".join([f"- {summary}" for summary in doc_summaries[:5]])  # 상위 5개만
        
        prompt = f"""임베딩된 문서들을 분석하여 다양한 사용자 질문을 생성하세요.

문서 정보:
{docs_info}

요구사항:
1. 구체적 정보 추출 질문 (specific_info): 5개
   - 예: "ACRSA의 화학 구조는?", "실험에서 사용한 온도 조건은?"
2. 요약 질문 (summary): 3개
   - 예: "이 논문의 핵심 내용을 요약해줘"
3. 비교 질문 (comparison): 2개
   - 예: "ACRSA와 다른 TADF 재료의 차이점은?"
4. 관계/인과관계 질문 (relationship): 3개
   - 예: "TADF 재료의 구조가 성능에 미치는 영향은?"
5. 다중 문서 교차 질문: 2개
   - 예: "여러 논문에서 공통적으로 언급한 내용은?"

각 질문은 실제 사용자가 물어볼 법한 자연스러운 형식으로 작성하세요.
답변 형식: JSON 배열 ["질문1", "질문2", ...]

질문 리스트:"""
        
        response = rag_chain.llm.invoke(prompt)
        
        # 응답 파싱
        if hasattr(response, 'content'):
            response_text = response.content
        elif hasattr(response, 'text'):
            response_text = response.text
        else:
            response_text = str(response)
        
        # JSON 추출
        import re
        json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
        if json_match:
            questions = json.loads(json_match.group())
        else:
            # JSON 형식이 아닌 경우 줄 단위로 추출
            lines = [line.strip().strip('"[]') for line in response_text.split('\n')]
            questions = [q for q in lines if q and len(q) > 5][:num_questions]
        
        print(f"✅ {len(questions)}개 질문 생성 완료")
        return questions[:num_questions]
        
    except Exception as e:
        print(f"⚠️ LLM 질문 생성 실패: {e}")
        return []


def get_manual_questions() -> List[Dict[str, str]]:
    """수동 질문 리스트 (실사용자 시나리오 기반)"""
    questions = [
        # 구체적 정보 추출
        {"question": "논문에서 사용한 TADF 재료는 무엇인가?", "category": "specific_info"},
        {"question": "ACRSA의 화학 구조는?", "category": "specific_info"},
        {"question": "실험에서 사용한 온도 조건은?", "category": "specific_info"},
        {"question": "최고 효율을 보인 재료는?", "category": "specific_info"},
        {"question": "논문에서 제시한 성능 지표의 수치는?", "category": "specific_info"},
        {"question": "실험에 사용된 장치의 종류는?", "category": "specific_info"},
        
        # 요약
        {"question": "이 논문의 핵심 내용을 3줄로 요약해줘", "category": "summary"},
        {"question": "실험 방법론을 요약해줘", "category": "summary"},
        {"question": "결론 부분을 요약해줘", "category": "summary"},
        {"question": "여러 논문의 주요 연구 결과를 요약해줘", "category": "summary"},
        
        # 비교
        {"question": "ACRSA와 다른 TADF 재료의 차이점은?", "category": "comparison"},
        {"question": "여러 논문에서 제시한 효율 수치를 비교해줘", "category": "comparison"},
        {"question": "다양한 TADF 재료의 장단점을 비교해줘", "category": "comparison"},
        
        # 관계/인과관계
        {"question": "TADF 재료의 구조가 성능에 미치는 영향은?", "category": "relationship"},
        {"question": "온도와 효율의 상관관계는?", "category": "relationship"},
        {"question": "분자 구조와 발광 메커니즘의 관계는?", "category": "relationship"},
        
        # 다중 문서 교차
        {"question": "여러 논문에서 공통적으로 언급한 내용은?", "category": "multi_doc"},
        {"question": "다양한 논문에서 제시한 연구 방법의 차이점은?", "category": "multi_doc"},
        {"question": "여러 연구에서 일치하거나 다른 결과는?", "category": "multi_doc"},
        
        # 실사용자 시나리오
        {"question": "이 주제에 대한 연구 배경을 설명해줘", "category": "general"},
        {"question": "최신 연구 동향은?", "category": "general"},
        {"question": "이 연구의 한계점은?", "category": "general"},
        {"question": "향후 연구 방향은?", "category": "general"},
    ]
    
    return questions


def run_comprehensive_test():
    """종합 테스트 실행"""
    print_header("실사용자 종합 테스트")
    
    cfg = ConfigManager()
    conf = cfg.get_all()
    
    # 1. 벡터스토어 초기화
    print("\n[1/5] 벡터스토어 초기화")
    vector_store = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=conf.get("embedding_api_type"),
        embedding_base_url=conf.get("embedding_base_url"),
        embedding_model=conf.get("embedding_model"),
        embedding_api_key=conf.get("embedding_api_key", "")
    )
    
    # 기존 문서 확인
    existing_docs = vector_store.get_documents_list()
    print(f"임베딩된 문서: {len(existing_docs)}개")
    if existing_docs:
        print("문서 목록:")
        for doc in existing_docs:
            print(f"  - {doc.get('file_name', 'Unknown')} ({doc.get('chunk_count', 0)}개 청크)")
    else:
        print("⚠️ 임베딩된 문서가 없습니다.")
        print("먼저 download_and_embed_multiple_pdfs.py를 실행하세요.")
        return None
    
    # 2. RAG 체인 초기화
    print("\n[2/5] RAG 체인 초기화")
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
    
    # 3. 질문 생성
    print_header("[3/5] 질문 생성")
    
    # 3.1 문서 요약 생성 (LLM 질문 생성용)
    doc_summaries = [f"{doc.get('file_name', 'Unknown')} ({doc.get('chunk_count', 0)} chunks)" 
                     for doc in existing_docs[:5]]
    
    # 3.2 LLM 자동 질문 생성
    llm_questions = generate_questions_with_llm(rag_chain, doc_summaries, num_questions=15)
    
    # 3.3 수동 질문 리스트
    manual_questions = get_manual_questions()
    
    # 3.4 질문 통합
    all_questions = []
    
    # LLM 질문 추가 (카테고리 자동 추정)
    for q in llm_questions:
        all_questions.append({
            "question": q,
            "category": "auto_generated",
            "source": "llm"
        })
    
    # 수동 질문 추가
    for q_dict in manual_questions:
        all_questions.append({
            "question": q_dict["question"],
            "category": q_dict["category"],
            "source": "manual"
        })
    
    print(f"\n총 질문 수: {len(all_questions)}개")
    print(f"  - LLM 자동 생성: {len(llm_questions)}개")
    print(f"  - 수동 리스트: {len(manual_questions)}개")
    
    # 4. 테스트 실행
    print_header("[4/5] 테스트 실행")
    
    results = []
    total_questions = len(all_questions)
    
    for i, q_info in enumerate(all_questions, 1):
        question = q_info["question"]
        category = q_info["category"]
        source = q_info["source"]
        
        print(f"\n{'='*80}")
        print(f"질문 #{i}/{total_questions} [{category}] [{source}]")
        print(f"{'='*80}")
        print(f"Q: {question}")
        print(f"{'='*80}")
        
        try:
            start_time = time.time()
            
            # 답변 생성
            result = rag_chain.query(question, chat_history=[])
            
            elapsed_time = time.time() - start_time
            
            answer = result.get("answer", "")
            confidence = result.get("confidence", 0.0)
            sources = result.get("sources", [])
            success = result.get("success", False)
            
            print(f"\n답변:")
            print(f"{answer[:500]}..." if len(answer) > 500 else answer)
            print(f"\n신뢰도: {confidence:.1f}%")
            print(f"출처: {len(sources)}개")
            print(f"소요 시간: {elapsed_time:.2f}초")
            
            # 출처 정보
            if sources:
                print(f"\n출처 문서:")
                for idx, source in enumerate(sources[:3], 1):  # 상위 3개만 표시
                    print(f"  {idx}. {source.get('file_name', 'Unknown')} (페이지: {source.get('page_number', 'Unknown')}, 유사도: {source.get('similarity_score', 0):.1f}%)")
            
            results.append({
                "question": question,
                "category": category,
                "source": source,
                "answer": answer,
                "confidence": confidence,
                "num_sources": len(sources),
                "sources": sources[:5],  # 상위 5개만 저장
                "elapsed_time": elapsed_time,
                "success": success
            })
            
        except Exception as e:
            print(f"❌ 오류: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "question": question,
                "category": category,
                "source": source,
                "answer": f"오류: {str(e)}",
                "confidence": 0.0,
                "num_sources": 0,
                "sources": [],
                "elapsed_time": 0.0,
                "success": False
            })
    
    # 5. 결과 분석 및 저장
    print_header("[5/5] 결과 분석")
    
    # 통계 계산
    total_questions = len(results)
    successful = sum(1 for r in results if r.get("success", False))
    avg_confidence = sum(r.get("confidence", 0) for r in results) / total_questions if total_questions > 0 else 0
    avg_time = sum(r.get("elapsed_time", 0) for r in results) / total_questions if total_questions > 0 else 0
    
    # 카테고리별 통계
    category_stats = {}
    for result in results:
        cat = result.get("category", "unknown")
        if cat not in category_stats:
            category_stats[cat] = {
                "count": 0,
                "avg_confidence": 0.0,
                "total_confidence": 0.0
            }
        category_stats[cat]["count"] += 1
        category_stats[cat]["total_confidence"] += result.get("confidence", 0)
    
    for cat in category_stats:
        cat_count = category_stats[cat]["count"]
        category_stats[cat]["avg_confidence"] = category_stats[cat]["total_confidence"] / cat_count if cat_count > 0 else 0
    
    # 통계 출력
    print(f"\n전체 통계:")
    print(f"  총 질문 수: {total_questions}")
    print(f"  성공: {successful} ({successful/total_questions*100:.1f}%)")
    print(f"  평균 신뢰도: {avg_confidence:.1f}%")
    print(f"  평균 소요 시간: {avg_time:.2f}초")
    
    print(f"\n카테고리별 통계:")
    for cat, stats in sorted(category_stats.items()):
        print(f"  {cat}: {stats['count']}개, 평균 신뢰도: {stats['avg_confidence']:.1f}%")
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"test_reports/comprehensive_user_test_{timestamp}.json"
    os.makedirs("test_reports", exist_ok=True)
    
    test_report = {
        "timestamp": timestamp,
        "total_questions": total_questions,
        "successful": successful,
        "avg_confidence": avg_confidence,
        "avg_time": avg_time,
        "category_stats": category_stats,
        "existing_documents": existing_docs,
        "results": results
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(test_report, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 테스트 결과 저장: {output_file}")
    
    # 질문-답변 쌍 출력
    print_header("질문-답변 쌍 요약")
    print("\n질문 → 답변 (상위 10개):")
    for i, result in enumerate(results[:10], 1):
        question = result["question"]
        answer = result["answer"]
        confidence = result["confidence"]
        
        print(f"\n[{i}] Q: {question}")
        print(f"    A: {answer[:200]}..." if len(answer) > 200 else f"    A: {answer}")
        print(f"    신뢰도: {confidence:.1f}%")
    
    return test_report


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 100)
    print("실사용자 종합 테스트")
    print("=" * 100)
    
    try:
        report = run_comprehensive_test()
        
        print("\n" + "=" * 100)
        print("테스트 완료!")
        print("=" * 100)
        
        return 0
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

