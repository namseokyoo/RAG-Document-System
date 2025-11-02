#!/usr/bin/env python
"""reference_result.json을 사용한 성능 테스트"""
import sys
import os
import json
import time
from typing import List, Dict

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ensure project root on sys.path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def load_reference_answers(filepath: str = "data/reference_result.json") -> List[Dict]:
    """기준 답변 세트 로드"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # [cite_start] 태그 제거 (JSON 파싱 전)
    content = content.replace('[cite_start]', '')
    
    # JSON 파싱
    data = json.loads(content)
    
    # 추가: 텍스트 내부의 [cite_start]도 제거
    for item in data:
        if '답변' in item:
            item['답변'] = item['답변'].replace('[cite_start]', '')
        if '출처' in item:
            for source in item['출처']:
                if '인용' in source:
                    source['인용'] = source['인용'].replace('[cite_start]', '')
    
    return data


def test_with_reference():
    """기준 답변 세트를 사용한 성능 테스트"""
    print("=" * 80)
    print("RAG 시스템 성능 테스트 (기준 답변 세트 사용)")
    print("=" * 80)
    
    # 설정 로드
    print(f"\n[설정 로드 중...]")
    config = ConfigManager().get_all()
    print(f"  LLM: {config['llm_model']}")
    print(f"  임베딩: {config['embedding_model']}")
    print(f"  청크 크기: {config['chunk_size']}")
    print(f"  Top K: {config['top_k']}")
    print(f"  Reranker: {config['use_reranker']} ({config.get('reranker_model', 'N/A')})")
    
    # 기준 답변 세트 로드
    print(f"\n[기준 답변 세트 로드 중...]")
    try:
        reference_qas = load_reference_answers()
        print(f"  ✓ 총 {len(reference_qas)}개 질문 로드됨")
    except FileNotFoundError:
        print(f"  ✗ 오류: reference_result.json 파일을 찾을 수 없습니다")
        return
    except json.JSONDecodeError as e:
        print(f"  ✗ 오류: JSON 파싱 실패 - {e}")
        return
    
    # VectorStore 및 RAG 초기화
    print(f"\n[RAG 시스템 초기화 중...]")
    try:
        vector_manager = VectorStoreManager(
            persist_directory="data/chroma_db",
            embedding_api_type=config.get("embedding_api_type", "ollama"),
            embedding_base_url=config.get("embedding_base_url"),
            embedding_model=config.get("embedding_model"),
            embedding_api_key=config.get("embedding_api_key", "")
        )
        multi_query_num = int(config.get("multi_query_num", 3))
        enable_multi_query = config.get("enable_multi_query", True) and multi_query_num > 0
        
        rag_chain = RAGChain(
            vectorstore=vector_manager.get_vectorstore(),
            llm_api_type=config.get("llm_api_type", "ollama"),
            llm_base_url=config.get("llm_base_url"),
            llm_model=config.get("llm_model"),
            llm_api_key=config.get("llm_api_key", ""),
            temperature=config.get("temperature", 0.7),
            top_k=config.get("top_k", 3),
            use_reranker=config.get("use_reranker", True),
            reranker_model=config.get("reranker_model"),
            reranker_initial_k=config.get("reranker_initial_k", 20),
            enable_synonym_expansion=config.get("enable_synonym_expansion", True),
            enable_multi_query=enable_multi_query,
            multi_query_num=multi_query_num
        )
        print("  ✓ 초기화 완료")
    except Exception as e:
        print(f"  ✗ 초기화 실패: {e}")
        return
    
    # 테스트 실행
    print(f"\n[테스트 시작]")
    print("=" * 80)
    
    results = []
    for i, qa_pair in enumerate(reference_qas, 1):
        question = qa_pair['질문']
        reference_answer = qa_pair.get('답변', '답변 없음')
        
        print(f"\n질문 {i}/{len(reference_qas)}: {question}")
        print("-" * 80)
        
        start = time.time()
        try:
            # RAG 응답 생성
            answer_parts = []
            for part in rag_chain.query_stream(question, chat_history=[]):
                answer_parts.append(part)
            generated_answer = "".join(answer_parts)
            
            elapsed = time.time() - start
            
            # 검색된 문서 수
            num_docs = len(rag_chain._last_retrieved_docs) if hasattr(rag_chain, '_last_retrieved_docs') else 0
            
            print(f"응답 시간: {elapsed:.2f}초")
            print(f"검색 문서 수: {num_docs}개")
            print(f"\n생성된 답변:\n{generated_answer[:300]}...")
            
            results.append({
                "question": question,
                "reference_answer": reference_answer,
                "generated_answer": generated_answer,
                "response_time": elapsed,
                "num_docs_retrieved": num_docs,
                "status": "success"
            })
            
        except Exception as e:
            print(f"  ✗ 오류 발생: {e}")
            results.append({
                "question": question,
                "reference_answer": reference_answer,
                "error": str(e),
                "status": "failed"
            })
    
    # 결과 요약
    print("\n" + "=" * 80)
    print("[테스트 결과 요약]")
    print("=" * 80)
    
    successful = [r for r in results if r.get("status") == "success"]
    failed = [r for r in results if r.get("status") == "failed"]
    
    if successful:
        avg_time = sum(r['response_time'] for r in successful) / len(successful)
        avg_docs = sum(r['num_docs_retrieved'] for r in successful) / len(successful)
        print(f"\n성공: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")
        print(f"평균 응답 시간: {avg_time:.2f}초")
        print(f"평균 검색 문서 수: {avg_docs:.1f}개")
    else:
        print("\n성공한 테스트가 없습니다.")
    
    if failed:
        print(f"\n실패: {len(failed)}개")
        for r in failed:
            print(f"  - {r['question'][:50]}...")
    
    # 결과 저장
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    output_file = f"test_results_{timestamp}.json"
    
    # 전체 결과를 더 상세한 형태로 저장
    output_data = {
        "test_config": {
            "temperature": config.get("temperature", 0.7),
            "chunk_size": config.get("chunk_size", 1500),
            "top_k": config.get("top_k", 5),
            "enable_multi_query": config.get("enable_multi_query", True),
            "multi_query_num": int(config.get("multi_query_num", 3)),
            "reranker": config.get("use_reranker", True),
            "reranker_model": config.get("reranker_model", "multilingual-mini"),
            "timestamp": timestamp
        },
        "summary": {
            "total_questions": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful)/len(results)*100 if results else 0,
            "avg_response_time": avg_time if successful else 0,
            "avg_docs_retrieved": avg_docs if successful else 0
        },
        "results": results
    }
    
    print(f"\n[결과 저장 중...]")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ 저장 완료: {output_file}")
        print(f"  파일 크기: {os.path.getsize(output_file) / 1024:.1f} KB")
    except Exception as e:
        print(f"  ✗ 저장 실패: {e}")
    
    print("\n" + "=" * 80)
    print("테스트 완료!")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    test_with_reference()

