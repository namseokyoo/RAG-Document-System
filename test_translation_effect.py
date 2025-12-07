"""
질문 번역 효과 테스트 스크립트
- 영어 통일 전후 비교
- 질문 번역 적용 여부 확인
- 검색 결과 청크 타입 분포 변화 확인
"""
import sys
import os
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def test_with_translation():
    """질문 번역이 적용된 상태로 테스트"""
    print("=" * 80)
    print("질문 번역 적용 후 검색 결과 분석")
    print("=" * 80)
    
    try:
        config_manager = ConfigManager()
        config = config_manager.get_all()
        
        # VectorStoreManager 초기화
        vectorstore = VectorStoreManager(
            persist_directory=config.get("persist_directory", "data/chroma_db"),
            embedding_api_type=config.get("embedding_api_type", "ollama"),
            embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
            embedding_model=config.get("embedding_model", "mxbai-embed-large"),
            embedding_api_key=config.get("embedding_api_key", ""),
            shared_db_path=config.get("shared_db_path"),
            shared_db_enabled=config.get("shared_db_enabled", False),
            distance_function=config.get("distance_function", "l2")
        )
        
        # RAGChain 초기화 (질문 번역 활성화)
        rag_chain = RAGChain(
            vectorstore=vectorstore,
            llm_api_type=config.get("llm_api_type", "ollama"),
            llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
            llm_model=config.get("llm_model", "llama3"),
            llm_api_key=config.get("llm_api_key", ""),
            use_reranker=True,
            reranker_model=config.get("reranker_model", "multilingual-mini"),
            enable_multi_query=True,
            enable_query_decomposition=True,
            enable_hyde=True
        )
        
        # 테스트 쿼리 (한글)
        test_query_kr = "TADF 재료와 OLED 효율의 관계"
        
        print(f"\n테스트 쿼리 (한글): {test_query_kr}\n")
        
        # 컨텍스트 검색 수행 (질문 번역 포함)
        print("[1단계] 컨텍스트 검색 시작...")
        context = rag_chain._get_context(test_query_kr, search_mode="integrated")
        
        # 검색 결과 분석
        if hasattr(rag_chain, '_last_retrieved_docs') and rag_chain._last_retrieved_docs:
            results = rag_chain._last_retrieved_docs
            print(f"\n[검색 결과] 총 {len(results)}개 문서\n")
            
            # 청크 타입별 통계
            chunk_type_stats = {}
            chunk_type_scores = {}
            
            for doc, score in results:
                chunk_type = doc.metadata.get('chunk_type', 'unknown')
                chunk_type_stats[chunk_type] = chunk_type_stats.get(chunk_type, 0) + 1
                
                if chunk_type not in chunk_type_scores:
                    chunk_type_scores[chunk_type] = []
                chunk_type_scores[chunk_type].append(float(score))
            
            # 타입별 통계 출력
            print("[청크 타입별 개수]")
            for chunk_type, count in sorted(chunk_type_stats.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(results)) * 100 if results else 0
                print(f"  {chunk_type}: {count}개 ({percentage:.2f}%)")
            
            # 타입별 점수 분석
            print("\n[청크 타입별 점수 분석]")
            for chunk_type in sorted(chunk_type_scores.keys()):
                scores = chunk_type_scores[chunk_type]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    min_score = min(scores)
                    max_score = max(scores)
                    print(f"  {chunk_type}:")
                    print(f"    평균: {avg_score:.4f}")
                    print(f"    최소: {min_score:.4f}")
                    print(f"    최대: {max_score:.4f}")
                    print(f"    개수: {len(scores)}개")
            
            # 텍스트 vs 비전 비교
            text_types = ['pdf_page_text', 'text_chunk', 'paragraph']
            vision_types = ['pdf_page_vision', 'slide_vision']
            
            text_results = [(doc, score) for doc, score in results 
                           if doc.metadata.get('chunk_type') in text_types]
            vision_results = [(doc, score) for doc, score in results 
                             if doc.metadata.get('chunk_type') in vision_types]
            
            print(f"\n[텍스트 vs 비전 비교]")
            if text_results:
                text_scores = [float(score) for _, score in text_results]
                text_avg = sum(text_scores) / len(text_scores)
                print(f"  텍스트 청크: {len(text_results)}개, 평균 점수: {text_avg:.4f}")
            
            if vision_results:
                vision_scores = [float(score) for _, score in vision_results]
                vision_avg = sum(vision_scores) / len(vision_scores)
                if text_results:
                    print(f"  비전 청크: {len(vision_results)}개, 평균 점수: {vision_avg:.4f}")
                    print(f"  점수 차이: {abs(text_avg - vision_avg):.4f} ({'텍스트가 높음' if text_avg > vision_avg else '비전이 높음'})")
                else:
                    print(f"  비전 청크: {len(vision_results)}개, 평균 점수: {vision_avg:.4f}")
            
            # Question Classifier 번역 확인
            if hasattr(rag_chain, '_last_classification') and rag_chain._last_classification:
                classification = rag_chain._last_classification
                translated = classification.get('translated_question')
                if translated:
                    print(f"\n[질문 번역 확인]")
                    print(f"  원본: {test_query_kr}")
                    print(f"  번역: {translated}")
                else:
                    print(f"\n[질문 번역 확인] 번역된 질문이 없음")
            
            # 원본 질문 확인
            if hasattr(rag_chain, '_original_question'):
                print(f"\n[원본 질문 저장 확인]")
                print(f"  저장된 원본: {rag_chain._original_question}")
            
            return results, chunk_type_stats, chunk_type_scores
        else:
            print("검색 결과가 없습니다.")
            return None, None, None
            
    except Exception as e:
        print(f"테스트 오류: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def main():
    """메인 실행 함수"""
    print("\n" + "=" * 80)
    print("질문 번역 효과 테스트")
    print("=" * 80 + "\n")
    
    # 질문 번역 적용 후 테스트
    results, chunk_type_stats, chunk_type_scores = test_with_translation()
    
    # 최종 요약
    print("\n" + "=" * 80)
    print("최종 요약")
    print("=" * 80)
    
    if chunk_type_stats:
        text_types = ['pdf_page_text', 'text_chunk', 'paragraph']
        vision_types = ['pdf_page_vision', 'slide_vision']
        
        text_count = sum(chunk_type_stats.get(t, 0) for t in text_types)
        vision_count = sum(chunk_type_stats.get(t, 0) for t in vision_types)
        total = sum(chunk_type_stats.values())
        
        print(f"\n[최종 검색 결과] (총 {total}개)")
        print(f"  텍스트 청크: {text_count}개 ({(text_count/total*100):.1f}%)")
        print(f"  비전 청크: {vision_count}개 ({(vision_count/total*100):.1f}%)")
        
        if text_count > 0:
            print(f"\n✅ 텍스트 청크가 검색 결과에 포함됨!")
        else:
            print(f"\n⚠️ 텍스트 청크가 검색 결과에 없음")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()





