"""
벡터 스토어 청크 타입 분포 및 검색 결과 분석 스크립트
"""
import sys
import os
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

def analyze_chunk_distribution():
    """벡터 스토어의 전체 청크 타입 분포 분석"""
    print("=" * 80)
    print("1. 벡터 스토어 전체 청크 타입 분포 분석")
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
        
        # 청크 타입 분포 조회
        distribution = vectorstore.get_chunk_type_distribution(db_type="both")
        
        if distribution:
            total = sum(distribution.values())
            print(f"\n전체 청크 수: {total}개\n")
            
            # 타입별 통계
            for chunk_type, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total) * 100 if total > 0 else 0
                print(f"  {chunk_type}: {count}개 ({percentage:.2f}%)")
            
            # 텍스트 vs 비전 비교
            text_types = ['pdf_page_text', 'text_chunk', 'paragraph', 'heading', 'section', 'list', 'table']
            vision_types = ['pdf_page_vision', 'slide_vision']
            
            text_count = sum(distribution.get(t, 0) for t in text_types)
            vision_count = sum(distribution.get(t, 0) for t in vision_types)
            other_count = total - text_count - vision_count
            
            print(f"\n[요약]")
            print(f"  텍스트 기반 청크: {text_count}개 ({(text_count/total*100):.2f}%)")
            print(f"  비전 기반 청크: {vision_count}개 ({(vision_count/total*100):.2f}%)")
            print(f"  기타: {other_count}개 ({(other_count/total*100):.2f}%)")
            
            return distribution, text_count, vision_count
        else:
            print("청크 타입 분포를 가져올 수 없습니다.")
            return None, 0, 0
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None, 0, 0


def analyze_search_results(vectorstore, test_query="TADF 재료와 OLED 효율의 관계"):
    """검색 결과의 청크 타입 분포 및 점수 분석"""
    print("\n" + "=" * 80)
    print("2. 검색 결과 청크 타입 분포 및 점수 분석")
    print("=" * 80)
    print(f"테스트 쿼리: {test_query}\n")
    
    try:
        # RAGChain 초기화 (검색만 사용)
        config_manager = ConfigManager()
        config = config_manager.get_all()
        
        rag_chain = RAGChain(
            vectorstore=vectorstore,
            llm_api_type=config.get("llm_api_type", "ollama"),
            llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
            llm_model=config.get("llm_model", "llama3"),
            llm_api_key=config.get("llm_api_key", ""),
            use_reranker=False,  # Re-ranker 없이 검색만
            enable_multi_query=False,  # 단일 쿼리로 테스트
            enable_query_decomposition=False
        )
        
        # 검색 수행
        results = rag_chain._search_candidates(test_query, search_mode="integrated")
        
        if not results:
            print("검색 결과가 없습니다.")
            return
        
        print(f"검색 결과: {len(results)}개\n")
        
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
                median_score = sorted(scores)[len(scores) // 2]
                print(f"  {chunk_type}:")
                print(f"    평균: {avg_score:.4f}")
                print(f"    중앙값: {median_score:.4f}")
                print(f"    최소: {min_score:.4f}")
                print(f"    최대: {max_score:.4f}")
                print(f"    개수: {len(scores)}개")
        
        # 텍스트 vs 비전 비교
        text_types = ['pdf_page_text', 'text_chunk', 'paragraph', 'heading', 'section', 'list', 'table']
        vision_types = ['pdf_page_vision', 'slide_vision']
        
        text_results = [(doc, score) for doc, score in results 
                       if doc.metadata.get('chunk_type') in text_types]
        vision_results = [(doc, score) for doc, score in results 
                         if doc.metadata.get('chunk_type') in vision_types]
        
        if text_results:
            text_scores = [float(score) for _, score in text_results]
            text_avg = sum(text_scores) / len(text_scores)
            print(f"\n[텍스트 vs 비전 비교]")
            print(f"  텍스트 청크: {len(text_results)}개, 평균 점수: {text_avg:.4f}")
        
        if vision_results:
            vision_scores = [float(score) for _, score in vision_results]
            vision_avg = sum(vision_scores) / len(vision_scores)
            if text_results:
                print(f"  비전 청크: {len(vision_results)}개, 평균 점수: {vision_avg:.4f}")
                print(f"  점수 차이: {abs(text_avg - vision_avg):.4f} ({'텍스트가 높음' if text_avg > vision_avg else '비전이 높음'})")
            else:
                print(f"  비전 청크: {len(vision_results)}개, 평균 점수: {vision_avg:.4f}")
        
        return results, chunk_type_stats, chunk_type_scores
        
    except Exception as e:
        print(f"검색 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def analyze_reranker_comparison(vectorstore, test_query="TADF 재료와 OLED 효율의 관계"):
    """Re-ranker 전후 점수 비교 분석"""
    print("\n" + "=" * 80)
    print("3. Re-ranker 전후 점수 비교 분석")
    print("=" * 80)
    print(f"테스트 쿼리: {test_query}\n")
    
    try:
        config_manager = ConfigManager()
        config = config_manager.get_all()
        
        # Re-ranker 사용하는 RAGChain
        rag_chain = RAGChain(
            vectorstore=vectorstore,
            llm_api_type=config.get("llm_api_type", "ollama"),
            llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
            llm_model=config.get("llm_model", "llama3"),
            llm_api_key=config.get("llm_api_key", ""),
            use_reranker=True,
            reranker_model=config.get("reranker_model", "multilingual-mini"),
            enable_multi_query=False,
            enable_query_decomposition=False
        )
        
        # 검색 수행 (Re-ranker 없이)
        search_results = rag_chain._search_candidates(test_query, search_mode="integrated")
        
        if not search_results:
            print("검색 결과가 없습니다.")
            return
        
        # 상위 20개 선택 (Re-ranker 입력)
        top_20 = search_results[:20]
        
        print(f"[Re-ranker 입력] 상위 20개 청크")
        text_types = ['pdf_page_text', 'text_chunk', 'paragraph']
        vision_types = ['pdf_page_vision', 'slide_vision']
        
        text_before = [(doc, score) for doc, score in top_20 
                      if doc.metadata.get('chunk_type') in text_types]
        vision_before = [(doc, score) for doc, score in top_20 
                        if doc.metadata.get('chunk_type') in vision_types]
        
        print(f"  텍스트 청크: {len(text_before)}개")
        if text_before:
            text_scores_before = [float(score) for _, score in text_before]
            print(f"    평균 점수: {sum(text_scores_before) / len(text_scores_before):.4f}")
            print(f"    점수 범위: {min(text_scores_before):.4f} ~ {max(text_scores_before):.4f}")
        
        print(f"  비전 청크: {len(vision_before)}개")
        if vision_before:
            vision_scores_before = [float(score) for _, score in vision_before]
            print(f"    평균 점수: {sum(vision_scores_before) / len(vision_scores_before):.4f}")
            print(f"    점수 범위: {min(vision_scores_before):.4f} ~ {max(vision_scores_before):.4f}")
        
        # Re-ranker 적용
        from utils.reranker import get_reranker
        reranker = get_reranker(model_name=config.get("reranker_model", "multilingual-mini"))
        
        docs_for_rerank = [{
            "page_content": doc.page_content,
            "metadata": doc.metadata,
            "vector_score": score,
            "document": doc
        } for doc, score in top_20]
        
        reranked = reranker.rerank(test_query, docs_for_rerank, top_k=20)
        
        print(f"\n[Re-ranker 출력] 상위 20개 청크")
        
        text_after = []
        vision_after = []
        
        for doc_dict in reranked:
            doc = doc_dict["document"]
            rerank_score = doc_dict.get("rerank_score", 0)
            chunk_type = doc.metadata.get('chunk_type', 'unknown')
            
            if chunk_type in text_types:
                text_after.append((doc, rerank_score))
            elif chunk_type in vision_types:
                vision_after.append((doc, rerank_score))
        
        print(f"  텍스트 청크: {len(text_after)}개")
        if text_after:
            text_scores_after = [float(score) for _, score in text_after]
            print(f"    평균 점수: {sum(text_scores_after) / len(text_scores_after):.4f}")
            print(f"    점수 범위: {min(text_scores_after):.4f} ~ {max(text_scores_after):.4f}")
        else:
            print("    (텍스트 청크 없음)")
        
        print(f"  비전 청크: {len(vision_after)}개")
        if vision_after:
            vision_scores_after = [float(score) for _, score in vision_after]
            print(f"    평균 점수: {sum(vision_scores_after) / len(vision_scores_after):.4f}")
            print(f"    점수 범위: {min(vision_scores_after):.4f} ~ {max(vision_scores_after):.4f}")
        
        # 제외된 텍스트 청크 분석
        if text_before and not text_after:
            print(f"\n[제외된 텍스트 청크 분석]")
            print(f"  Re-ranker 전: {len(text_before)}개")
            print(f"  Re-ranker 후: {len(text_after)}개")
            print(f"  제외된 개수: {len(text_before) - len(text_after)}개")
            
            # 제외된 청크의 원래 점수
            excluded = []
            for doc, score in text_before:
                # Re-ranker 결과에서 찾기
                found = False
                for doc_dict in reranked:
                    if doc_dict["document"] == doc:
                        found = True
                        break
                if not found:
                    excluded.append((doc.metadata.get('file_name', 'Unknown'), float(score)))
            
            if excluded:
                excluded.sort(key=lambda x: x[1], reverse=True)
                print(f"\n  제외된 텍스트 청크 (점수 순):")
                for name, score in excluded[:5]:  # 상위 5개만
                    print(f"    {name}: {score:.4f}")
        
        return text_before, text_after, vision_before, vision_after
        
    except Exception as e:
        print(f"Re-ranker 비교 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None


def main():
    """메인 실행 함수"""
    print("\n" + "=" * 80)
    print("벡터 스토어 청크 타입 분포 및 검색 결과 분석")
    print("=" * 80 + "\n")
    
    # 1. 벡터 스토어 전체 분포 분석
    distribution, text_count, vision_count = analyze_chunk_distribution()
    
    if distribution is None:
        print("벡터 스토어 분석 실패. 종료합니다.")
        return
    
    # 2. 검색 결과 분석
    config_manager = ConfigManager()
    config = config_manager.get_all()
    
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
    
    test_query = "TADF 재료와 OLED 효율의 관계"
    search_results, chunk_type_stats, chunk_type_scores = analyze_search_results(vectorstore, test_query)
    
    # 3. Re-ranker 비교 분석
    text_before, text_after, vision_before, vision_after = analyze_reranker_comparison(vectorstore, test_query)
    
    # 최종 요약
    print("\n" + "=" * 80)
    print("최종 요약")
    print("=" * 80)
    
    total_chunks = sum(distribution.values())
    print(f"\n1. 벡터 스토어 전체 분포:")
    print(f"   텍스트 청크: {text_count}개 ({(text_count/total_chunks*100):.2f}%)")
    print(f"   비전 청크: {vision_count}개 ({(vision_count/total_chunks*100):.2f}%)")
    
    if chunk_type_stats:
        text_in_search = sum(chunk_type_stats.get(t, 0) for t in ['pdf_page_text', 'text_chunk', 'paragraph'])
        vision_in_search = sum(chunk_type_stats.get(t, 0) for t in ['pdf_page_vision', 'slide_vision'])
        print(f"\n2. 검색 결과 분포 (상위 {len(search_results) if search_results else 0}개):")
        print(f"   텍스트 청크: {text_in_search}개")
        print(f"   비전 청크: {vision_in_search}개")
        
        if text_in_search > 0 and chunk_type_scores:
            text_types = ['pdf_page_text', 'text_chunk', 'paragraph']
            text_scores = []
            for t in text_types:
                if t in chunk_type_scores:
                    text_scores.extend(chunk_type_scores[t])
            if text_scores:
                print(f"   텍스트 청크 평균 점수: {sum(text_scores) / len(text_scores):.4f}")
        
        vision_types = ['pdf_page_vision', 'slide_vision']
        vision_scores = []
        for t in vision_types:
            if t in chunk_type_scores:
                vision_scores.extend(chunk_type_scores[t])
        if vision_scores:
            print(f"   비전 청크 평균 점수: {sum(vision_scores) / len(vision_scores):.4f}")
    
    if text_before is not None:
        print(f"\n3. Re-ranker 전후 비교:")
        print(f"   Re-ranker 전 텍스트 청크: {len(text_before)}개")
        print(f"   Re-ranker 후 텍스트 청크: {len(text_after)}개")
        if len(text_before) > len(text_after):
            print(f"   → {len(text_before) - len(text_after)}개 텍스트 청크가 Re-ranker에서 제외됨")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()





