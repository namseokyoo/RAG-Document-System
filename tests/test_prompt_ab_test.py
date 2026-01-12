"""
프롬프트 개선 AB 테스트

기존 프롬프트와 개선된 프롬프트를 비교하여 답변 품질을 평가합니다.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from datetime import datetime
from typing import Dict, List
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
from config import ConfigManager

# 테스트 질문 세트 (다양한 유형 포함)
TEST_QUESTIONS = [
    {
        "question": "kFRET 값은?",
        "type": "simple",
        "description": "단순 사실 질문"
    },
    {
        "question": "TADF란 무엇인가?",
        "type": "normal",
        "description": "설명 질문"
    },
    {
        "question": "ACRSA와 DABNA1의 차이점은?",
        "type": "comparison",
        "description": "비교 질문"
    },
    {
        "question": "TADF 재료의 구조가 발광 효율에 미치는 영향은?",
        "type": "relationship",
        "description": "관계/인과관계 질문"
    },
    {
        "question": "OLED 효율 개선 방법을 요약해줘",
        "type": "summary",
        "description": "요약 질문"
    },
    {
        "question": "What is the synthesis temperature?",
        "type": "simple",
        "description": "정보 부족 질문 (영어)"
    }
]


def load_old_prompt_template():
    """기존 프롬프트 템플릿 로드 (백업 파일 또는 하드코딩)"""
    # 기존 프롬프트 (개선 전)
    return """You are a document-based AI assistant. Provide accurate and useful answers based on the provided documents.

Provided documents:
{context}

Previous conversation:
{chat_history}

Question:
{question}

---

Answer guidelines:

1. **Natural format**:
   - Write in natural paragraphs without section headings
   - Short answers (1-2 sentences) for simple questions, multiple paragraphs for complex questions
   - Answer according to user intent (translation/summary/explanation, etc.)
   - **If there are formulas, numbers, or symbols, extract them exactly as they appear in the original** (e.g., R ~ t^(1/3), Pe_C = χ_0 / M_0)

2. **Source indication**:
   - You can naturally mention file names (e.g., "According to Display_1801.pdf...")
   - However, do not use explicit labels like "Source:", "참고:", etc.
   - Do not use numbered citations ([1], [2], etc.)
   - The system will automatically add a reference document list

3. **Examples**:

Question: "What is the kFRET value?"
Answer: According to the provided documents, the kFRET value is approximately 87.8%. This represents the energy transfer efficiency between the fluorescent dopant and the host.

Question: "What is TADF?"
Answer: TADF (Thermally Activated Delayed Fluorescence) is a luminescence mechanism that thermally activates triplet excitons and converts them back to singlets. This theoretically achieves 100% internal quantum efficiency in OLEDs.

Question: "Translate the introduction"
Answer: Hybrid fluorescent OLED is a new architecture that combines TADF assistant host with fluorescent dopant. This approach simultaneously achieves high efficiency of TADF and excellent color purity of fluorescent dopant.

Question: "What does Pe_C represent?"
Answer: The chemotaxis Péclet number (Pe_C) represents the competition between directional chemotaxis and non-directional active diffusion. It is defined as Pe_C ≡ χ_0 / M_0.

Question: "What is the synthesis temperature?"
Answer: The documents describe the organic synthesis process, but the specific synthesis temperature is not specified.

4. **Important**:
   - Do not make speculations not based on documents. Answer only based on the document content.
   - If information cannot be confirmed from documents or previous conversations, explicitly state 'Not available in document'.
   - If there are mathematical formulas, inequalities, or relational expressions, quote them accurately.
   - **Respond in the same language as the question**. If the question is in Korean, respond in Korean. If the question is in English, respond in English.

Answer:"""


def analyze_answer(answer: str) -> Dict:
    """답변 분석"""
    word_count = len(answer.split())
    char_count = len(answer)
    sentence_count = answer.count('.') + answer.count('!') + answer.count('?')
    paragraph_count = answer.count('\n\n') + 1
    
    # 페이지 번호 포함 여부
    has_page_number = any(keyword in answer.lower() for keyword in ['page', '페이지', 'slide', '슬라이드'])
    
    # 출처 표시 여부
    has_source = any(keyword in answer.lower() for keyword in ['according to', '에 따르면', '문서', 'document'])
    
    return {
        "word_count": word_count,
        "char_count": char_count,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "has_page_number": has_page_number,
        "has_source": has_source,
        "avg_words_per_sentence": word_count / max(sentence_count, 1)
    }


def run_ab_test(rag_chain: RAGChain, questions: List[Dict], use_new_prompt: bool = True):
    """AB 테스트 실행"""
    results = []
    
    print(f"\n{'='*80}")
    print(f"{'개선된 프롬프트' if use_new_prompt else '기존 프롬프트'} 테스트 시작")
    print(f"{'='*80}\n")
    
    for i, test_case in enumerate(questions, 1):
        question = test_case["question"]
        print(f"[{i}/{len(questions)}] {test_case['description']}: {question}")
        
        start_time = time.time()
        try:
            result = rag_chain.query(question, chat_history=[])
            answer = result.get("answer", "")
            elapsed_time = time.time() - start_time
            
            analysis = analyze_answer(answer)
            
            result_data = {
                "question": question,
                "type": test_case["type"],
                "description": test_case["description"],
                "answer": answer,
                "elapsed_time": elapsed_time,
                "analysis": analysis,
                "sources": result.get("sources", [])
            }
            
            results.append(result_data)
            
            print(f"  ✓ 완료 ({elapsed_time:.2f}초)")
            print(f"    - 단어 수: {analysis['word_count']}, 문장 수: {analysis['sentence_count']}")
            print(f"    - 페이지 번호 포함: {'✓' if analysis['has_page_number'] else '✗'}")
            print(f"    - 출처 표시: {'✓' if analysis['has_source'] else '✗'}")
            print()
            
        except Exception as e:
            print(f"  ✗ 오류: {e}\n")
            results.append({
                "question": question,
                "type": test_case["type"],
                "description": test_case["description"],
                "error": str(e),
                "elapsed_time": time.time() - start_time
            })
    
    return results


def compare_results(old_results: List[Dict], new_results: List[Dict]):
    """결과 비교 및 리포트 생성"""
    print("\n" + "="*80)
    print("AB 테스트 결과 비교")
    print("="*80 + "\n")
    
    comparison = []
    
    for old, new in zip(old_results, new_results):
        if "error" in old or "error" in new:
            continue
            
        old_analysis = old.get("analysis", {})
        new_analysis = new.get("analysis", {})
        
        comparison_item = {
            "question": old["question"],
            "type": old["type"],
            "old": {
                "word_count": old_analysis.get("word_count", 0),
                "sentence_count": old_analysis.get("sentence_count", 0),
                "has_page_number": old_analysis.get("has_page_number", False),
                "has_source": old_analysis.get("has_source", False),
                "elapsed_time": old.get("elapsed_time", 0)
            },
            "new": {
                "word_count": new_analysis.get("word_count", 0),
                "sentence_count": new_analysis.get("sentence_count", 0),
                "has_page_number": new_analysis.get("has_page_number", False),
                "has_source": new_analysis.get("has_source", False),
                "elapsed_time": new.get("elapsed_time", 0)
            }
        }
        
        # 변화율 계산
        old_words = old_analysis.get("word_count", 1)
        new_words = new_analysis.get("word_count", 1)
        word_change = ((new_words - old_words) / old_words * 100) if old_words > 0 else 0
        
        comparison_item["improvement"] = {
            "word_count_change": f"{word_change:+.1f}%",
            "sentence_count_change": new_analysis.get("sentence_count", 0) - old_analysis.get("sentence_count", 0),
            "page_number_added": new_analysis.get("has_page_number", False) and not old_analysis.get("has_page_number", False),
            "source_improved": new_analysis.get("has_source", False) and not old_analysis.get("has_source", False)
        }
        
        comparison.append(comparison_item)
        
        # 개별 결과 출력
        print(f"질문: {old['question']}")
        print(f"  기존: {old_analysis.get('word_count', 0)}단어, {old_analysis.get('sentence_count', 0)}문장")
        print(f"  개선: {new_analysis.get('word_count', 0)}단어, {new_analysis.get('sentence_count', 0)}문장")
        print(f"  변화: {word_change:+.1f}%")
        if comparison_item["improvement"]["page_number_added"]:
            print(f"  ✓ 페이지 번호 추가됨")
        if comparison_item["improvement"]["source_improved"]:
            print(f"  ✓ 출처 표시 개선됨")
        print()
    
    # 전체 통계
    print("\n" + "-"*80)
    print("전체 통계")
    print("-"*80)
    
    old_avg_words = sum(c["old"]["word_count"] for c in comparison) / len(comparison) if comparison else 0
    new_avg_words = sum(c["new"]["word_count"] for c in comparison) / len(comparison) if comparison else 0
    old_avg_sentences = sum(c["old"]["sentence_count"] for c in comparison) / len(comparison) if comparison else 0
    new_avg_sentences = sum(c["new"]["sentence_count"] for c in comparison) / len(comparison) if comparison else 0
    
    old_page_count = sum(1 for c in comparison if c["old"]["has_page_number"])
    new_page_count = sum(1 for c in comparison if c["new"]["has_page_number"])
    
    print(f"평균 단어 수: {old_avg_words:.1f} → {new_avg_words:.1f} ({((new_avg_words - old_avg_words) / old_avg_words * 100):+.1f}%)")
    print(f"평균 문장 수: {old_avg_sentences:.1f} → {new_avg_sentences:.1f} ({((new_avg_sentences - old_avg_sentences) / old_avg_sentences * 100):+.1f}%)")
    print(f"페이지 번호 포함: {old_page_count}/{len(comparison)} → {new_page_count}/{len(comparison)}")
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"tests/prompt_ab_test_results_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "test_questions": TEST_QUESTIONS,
            "old_results": old_results,
            "new_results": new_results,
            "comparison": comparison,
            "summary": {
                "old_avg_words": old_avg_words,
                "new_avg_words": new_avg_words,
                "old_avg_sentences": old_avg_sentences,
                "new_avg_sentences": new_avg_sentences,
                "old_page_count": old_page_count,
                "new_page_count": new_page_count
            }
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n결과가 저장되었습니다: {output_file}")
    
    return comparison


def main():
    """메인 함수"""
    print("="*80)
    print("프롬프트 개선 AB 테스트")
    print("="*80)
    print(f"테스트 질문 수: {len(TEST_QUESTIONS)}")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 설정 로드
    config_manager = ConfigManager()
    config = config_manager.get_all()
    
    # 벡터 스토어 초기화
    print("벡터 스토어 초기화 중...")
    vectorstore = VectorStoreManager(
        persist_directory=config.get("chroma_persist_directory", "data/chroma_db"),
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
        embedding_model=config.get("embedding_model", "mxbai-embed-large"),
        embedding_api_key=config.get("embedding_api_key", "")
    )
    
    # RAG 체인 초기화 (개선된 프롬프트 사용)
    print("RAG 체인 초기화 중...")
    rag_chain = RAGChain(
        vectorstore=vectorstore,
        llm_api_type=config.get("llm_api_type", "ollama"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "llama3"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.3),
        top_k=config.get("top_k", 3),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        enable_multi_query=config.get("enable_multi_query", True),
        multi_query_num=config.get("multi_query_num", 3),
        enable_hyde=config.get("enable_hyde", True),
        enable_query_decomposition=config.get("enable_query_decomposition", True)
    )
    
    print("\n⚠️  주의: 현재는 개선된 프롬프트만 테스트합니다.")
    print("기존 프롬프트와 비교하려면 백업 파일이 필요합니다.\n")
    
    # 개선된 프롬프트로 테스트
    new_results = run_ab_test(rag_chain, TEST_QUESTIONS, use_new_prompt=True)
    
    print("\n" + "="*80)
    print("테스트 완료")
    print("="*80)
    print(f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 결과 요약
    print("\n결과 요약:")
    total_words = sum(r.get("analysis", {}).get("word_count", 0) for r in new_results if "analysis" in r)
    total_sentences = sum(r.get("analysis", {}).get("sentence_count", 0) for r in new_results if "analysis" in r)
    avg_words = total_words / len([r for r in new_results if "analysis" in r]) if new_results else 0
    avg_sentences = total_sentences / len([r for r in new_results if "analysis" in r]) if new_results else 0
    
    print(f"  평균 단어 수: {avg_words:.1f}")
    print(f"  평균 문장 수: {avg_sentences:.1f}")
    print(f"  페이지 번호 포함: {sum(1 for r in new_results if r.get('analysis', {}).get('has_page_number', False))}/{len(new_results)}")
    print(f"  출처 표시: {sum(1 for r in new_results if r.get('analysis', {}).get('has_source', False))}/{len(new_results)}")


if __name__ == "__main__":
    main()

