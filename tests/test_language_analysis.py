"""
언어 불일치 분석 테스트 스크립트
- 텍스트 청크와 비전 청크의 언어 확인
- 벡터 검색 vs BM25 검색에서의 순위 비교
- 언어별 점수 분석
"""
import sys
import os
import re
from config import ConfigManager
from utils.vector_store import VectorStoreManager
from langchain.schema import Document

def detect_language(text):
    """텍스트의 언어 감지 (간단한 휴리스틱)"""
    if not text:
        return "unknown"
    
    # 한글 유니코드 범위: AC00-D7A3
    korean_pattern = re.compile(r'[가-힣]')
    # 영어 알파벳
    english_pattern = re.compile(r'[a-zA-Z]')
    
    korean_count = len(korean_pattern.findall(text))
    english_count = len(english_pattern.findall(text))
    total_chars = len(re.findall(r'[가-힣a-zA-Z]', text))
    
    if total_chars == 0:
        return "unknown"
    
    korean_ratio = korean_count / total_chars if total_chars > 0 else 0
    english_ratio = english_count / total_chars if total_chars > 0 else 0
    
    if korean_ratio > 0.3:
        return "korean"
    elif english_ratio > 0.3:
        return "english"
    else:
        return "mixed"

def analyze_chunk_languages(vectorstore):
    """청크 타입별 언어 분포 분석"""
    print("=" * 80)
    print("1. 청크 타입별 언어 분포 분석")
    print("=" * 80)
    
    try:
        # 모든 문서 가져오기
        all_docs = vectorstore.get_all_documents(db_type="both")
        
        chunk_type_languages = {}
        
        for doc in all_docs:
            chunk_type = doc.metadata.get('chunk_type', 'unknown')
            content = doc.page_content
            
            if chunk_type not in chunk_type_languages:
                chunk_type_languages[chunk_type] = {
                    'korean': 0,
                    'english': 0,
                    'mixed': 0,
                    'unknown': 0,
                    'total': 0
                }
            
            lang = detect_language(content)
            chunk_type_languages[chunk_type][lang] += 1
            chunk_type_languages[chunk_type]['total'] += 1
        
        print("\n[청크 타입별 언어 분포]")
        for chunk_type, lang_stats in sorted(chunk_type_languages.items()):
            total = lang_stats['total']
            if total == 0:
                continue
            
            print(f"\n  {chunk_type} (총 {total}개):")
            for lang in ['korean', 'english', 'mixed', 'unknown']:
                count = lang_stats[lang]
                if count > 0:
                    percentage = (count / total) * 100
                    print(f"    {lang}: {count}개 ({percentage:.2f}%)")
        
        return chunk_type_languages
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_vector_search_only(vectorstore, query):
    """벡터 검색만 수행하여 청크 타입별 순위 분석"""
    print("\n" + "=" * 80)
    print("2. 벡터 검색만 수행 (BM25 제외)")
    print("=" * 80)
    print(f"테스트 쿼리: {query}\n")
    
    try:
        # 벡터 검색만 수행
        vector_results = vectorstore.vectorstore.similarity_search_with_score(query, k=60)
        
        if not vector_results:
            print("벡터 검색 결과가 없습니다.")
            return None
        
        print(f"벡터 검색 결과: {len(vector_results)}개\n")
        
        # 청크 타입별 통계
        chunk_type_stats = {}
        chunk_type_scores = {}
        chunk_type_languages = {}
        
        for rank, (doc, score) in enumerate(vector_results, start=1):
            chunk_type = doc.metadata.get('chunk_type', 'unknown')
            content = doc.page_content
            lang = detect_language(content)
            
            if chunk_type not in chunk_type_stats:
                chunk_type_stats[chunk_type] = []
                chunk_type_scores[chunk_type] = []
                chunk_type_languages[chunk_type] = {'korean': 0, 'english': 0, 'mixed': 0, 'unknown': 0}
            
            chunk_type_stats[chunk_type].append(rank)
            chunk_type_scores[chunk_type].append(float(score))
            chunk_type_languages[chunk_type][lang] += 1
        
        print("[청크 타입별 벡터 검색 순위 분석]")
        for chunk_type in sorted(chunk_type_stats.keys()):
            ranks = chunk_type_stats[chunk_type]
            scores = chunk_type_scores[chunk_type]
            
            avg_rank = sum(ranks) / len(ranks)
            avg_score = sum(scores) / len(scores)
            min_rank = min(ranks)
            max_rank = max(ranks)
            
            print(f"\n  {chunk_type}:")
            print(f"    개수: {len(ranks)}개")
            print(f"    평균 순위: {avg_rank:.1f}")
            print(f"    최고 순위: {min_rank}위")
            print(f"    최저 순위: {max_rank}위")
            print(f"    평균 점수: {avg_score:.4f}")
            
            # 언어 분포
            lang_stats = chunk_type_languages[chunk_type]
            total = sum(lang_stats.values())
            if total > 0:
                print(f"    언어 분포:")
                for lang, count in lang_stats.items():
                    if count > 0:
                        print(f"      {lang}: {count}개 ({(count/total*100):.1f}%)")
        
        return vector_results, chunk_type_stats, chunk_type_scores
        
    except Exception as e:
        print(f"벡터 검색 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def analyze_bm25_search_only(vectorstore, query):
    """BM25 검색만 수행하여 청크 타입별 순위 분석"""
    print("\n" + "=" * 80)
    print("3. BM25 검색만 수행 (벡터 검색 제외)")
    print("=" * 80)
    print(f"테스트 쿼리: {query}\n")
    
    try:
        if not vectorstore.bm25_ready or vectorstore.bm25 is None:
            print("BM25 인덱스가 준비되지 않았습니다.")
            return None
        
        # BM25 검색 수행
        query_tokens = vectorstore._tokenize(query)
        bm25_scores = vectorstore.bm25.get_scores(query_tokens)
        
        # 상위 60개 선택
        bm25_sorted = sorted(list(enumerate(bm25_scores)), key=lambda x: x[1], reverse=True)[:60]
        
        print(f"BM25 검색 결과: {len(bm25_sorted)}개\n")
        
        # 문서 ID 매핑
        doc_id_to_idx = {}
        for idx, doc_id in enumerate(vectorstore.doc_ids):
            doc_id_to_idx[doc_id] = idx
        
        # 컬렉션에서 문서 정보 가져오기
        coll = vectorstore.vectorstore._collection
        data = coll.get()
        docs_raw = data.get("documents", [])
        metas_raw = data.get("metadatas", [])
        ids_raw = data.get("ids", [])
        
        id_to_index = {idv: i for i, idv in enumerate(ids_raw)}
        
        # 청크 타입별 통계
        chunk_type_stats = {}
        chunk_type_scores = {}
        chunk_type_languages = {}
        
        for rank, (idx, score) in enumerate(bm25_sorted, start=1):
            if idx >= len(vectorstore.doc_ids):
                continue
            
            doc_id = vectorstore.doc_ids[idx]
            
            # 문서 내용 가져오기
            if doc_id in id_to_index:
                doc_idx = id_to_index[doc_id]
                if doc_idx < len(docs_raw):
                    content = docs_raw[doc_idx]
                    metadata = metas_raw[doc_idx] if doc_idx < len(metas_raw) else {}
                    chunk_type = metadata.get('chunk_type', 'unknown')
                    lang = detect_language(content)
                    
                    if chunk_type not in chunk_type_stats:
                        chunk_type_stats[chunk_type] = []
                        chunk_type_scores[chunk_type] = []
                        chunk_type_languages[chunk_type] = {'korean': 0, 'english': 0, 'mixed': 0, 'unknown': 0}
                    
                    chunk_type_stats[chunk_type].append(rank)
                    chunk_type_scores[chunk_type].append(float(score))
                    chunk_type_languages[chunk_type][lang] += 1
        
        print("[청크 타입별 BM25 검색 순위 분석]")
        for chunk_type in sorted(chunk_type_stats.keys()):
            ranks = chunk_type_stats[chunk_type]
            scores = chunk_type_scores[chunk_type]
            
            avg_rank = sum(ranks) / len(ranks)
            avg_score = sum(scores) / len(scores)
            min_rank = min(ranks)
            max_rank = max(ranks)
            
            print(f"\n  {chunk_type}:")
            print(f"    개수: {len(ranks)}개")
            print(f"    평균 순위: {avg_rank:.1f}")
            print(f"    최고 순위: {min_rank}위")
            print(f"    최저 순위: {max_rank}위")
            print(f"    평균 점수: {avg_score:.4f}")
            
            # 언어 분포
            lang_stats = chunk_type_languages[chunk_type]
            total = sum(lang_stats.values())
            if total > 0:
                print(f"    언어 분포:")
                for lang, count in lang_stats.items():
                    if count > 0:
                        print(f"      {lang}: {count}개 ({(count/total*100):.1f}%)")
        
        return bm25_sorted, chunk_type_stats, chunk_type_scores
        
    except Exception as e:
        print(f"BM25 검색 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def compare_language_impact(vectorstore, query):
    """언어별 검색 성능 비교"""
    print("\n" + "=" * 80)
    print("4. 언어별 검색 성능 비교")
    print("=" * 80)
    print(f"테스트 쿼리: {query}\n")
    print(f"쿼리 언어: {detect_language(query)}\n")
    
    try:
        # 벡터 검색 결과
        vector_results = vectorstore.vectorstore.similarity_search_with_score(query, k=60)
        
        # 언어별로 그룹화
        korean_chunks = []
        english_chunks = []
        mixed_chunks = []
        
        for rank, (doc, score) in enumerate(vector_results, start=1):
            content = doc.page_content
            lang = detect_language(content)
            chunk_type = doc.metadata.get('chunk_type', 'unknown')
            
            chunk_info = {
                'rank': rank,
                'score': float(score),
                'chunk_type': chunk_type,
                'content_preview': content[:100] + '...' if len(content) > 100 else content
            }
            
            if lang == 'korean':
                korean_chunks.append(chunk_info)
            elif lang == 'english':
                english_chunks.append(chunk_info)
            else:
                mixed_chunks.append(chunk_info)
        
        print("[언어별 벡터 검색 성능]")
        if korean_chunks:
            avg_rank_kr = sum(c['rank'] for c in korean_chunks) / len(korean_chunks)
            avg_score_kr = sum(c['score'] for c in korean_chunks) / len(korean_chunks)
            print(f"\n  한글 청크: {len(korean_chunks)}개")
            print(f"    평균 순위: {avg_rank_kr:.1f}")
            print(f"    평균 점수: {avg_score_kr:.4f}")
            print(f"    청크 타입 분포:")
            kr_types = {}
            for c in korean_chunks:
                ct = c['chunk_type']
                kr_types[ct] = kr_types.get(ct, 0) + 1
            for ct, count in kr_types.items():
                print(f"      {ct}: {count}개")
        
        if english_chunks:
            avg_rank_en = sum(c['rank'] for c in english_chunks) / len(english_chunks)
            avg_score_en = sum(c['score'] for c in english_chunks) / len(english_chunks)
            print(f"\n  영어 청크: {len(english_chunks)}개")
            print(f"    평균 순위: {avg_rank_en:.1f}")
            print(f"    평균 점수: {avg_score_en:.4f}")
            print(f"    청크 타입 분포:")
            en_types = {}
            for c in english_chunks:
                ct = c['chunk_type']
                en_types[ct] = en_types.get(ct, 0) + 1
            for ct, count in en_types.items():
                print(f"      {ct}: {count}개")
        
        if korean_chunks and english_chunks:
            print(f"\n[비교]")
            print(f"  한글 청크 평균 순위: {avg_rank_kr:.1f} vs 영어 청크 평균 순위: {avg_rank_en:.1f}")
            if avg_rank_kr < avg_rank_en:
                print(f"  → 한글 청크가 평균 {avg_rank_en - avg_rank_kr:.1f}위 더 높음 (한글 질문에 유리)")
            else:
                print(f"  → 영어 청크가 평균 {avg_rank_kr - avg_rank_en:.1f}위 더 높음")
        
        return korean_chunks, english_chunks, mixed_chunks
        
    except Exception as e:
        print(f"언어별 비교 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def main():
    """메인 실행 함수"""
    print("\n" + "=" * 80)
    print("언어 불일치 분석 테스트")
    print("=" * 80 + "\n")
    
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
        
        # 테스트 쿼리
        test_query_kr = "TADF 재료와 OLED 효율의 관계"
        test_query_en = "relationship between TADF materials and OLED efficiency"
        
        # 1. 청크 타입별 언어 분포
        chunk_type_languages = analyze_chunk_languages(vectorstore)
        
        # 2. 벡터 검색만 수행 (한글 질문)
        print(f"\n{'='*80}")
        print("한글 질문으로 벡터 검색")
        print(f"{'='*80}")
        vector_results_kr, vector_stats_kr, vector_scores_kr = analyze_vector_search_only(vectorstore, test_query_kr)
        
        # 3. BM25 검색만 수행 (한글 질문)
        print(f"\n{'='*80}")
        print("한글 질문으로 BM25 검색")
        print(f"{'='*80}")
        bm25_results_kr, bm25_stats_kr, bm25_scores_kr = analyze_bm25_search_only(vectorstore, test_query_kr)
        
        # 4. 언어별 검색 성능 비교 (한글 질문)
        korean_chunks, english_chunks, mixed_chunks = compare_language_impact(vectorstore, test_query_kr)
        
        # 5. 영어 질문으로도 테스트
        print(f"\n{'='*80}")
        print("영어 질문으로 벡터 검색 (비교용)")
        print(f"{'='*80}")
        vector_results_en, vector_stats_en, vector_scores_en = analyze_vector_search_only(vectorstore, test_query_en)
        
        # 최종 요약
        print("\n" + "=" * 80)
        print("최종 요약")
        print("=" * 80)
        
        if chunk_type_languages:
            print("\n[청크 타입별 언어 분포]")
            for chunk_type, lang_stats in sorted(chunk_type_languages.items()):
                total = lang_stats['total']
                if total > 0:
                    kr_pct = (lang_stats['korean'] / total) * 100
                    en_pct = (lang_stats['english'] / total) * 100
                    print(f"  {chunk_type}: 한글 {kr_pct:.1f}%, 영어 {en_pct:.1f}%")
        
        if vector_stats_kr:
            print("\n[한글 질문 - 벡터 검색 순위]")
            for chunk_type in ['pdf_page_text', 'pdf_page_vision']:
                if chunk_type in vector_stats_kr:
                    ranks = vector_stats_kr[chunk_type]
                    avg_rank = sum(ranks) / len(ranks)
                    print(f"  {chunk_type}: 평균 {avg_rank:.1f}위 ({len(ranks)}개)")
        
        if bm25_stats_kr:
            print("\n[한글 질문 - BM25 검색 순위]")
            for chunk_type in ['pdf_page_text', 'pdf_page_vision']:
                if chunk_type in bm25_stats_kr:
                    ranks = bm25_stats_kr[chunk_type]
                    avg_rank = sum(ranks) / len(ranks)
                    print(f"  {chunk_type}: 평균 {avg_rank:.1f}위 ({len(ranks)}개)")
        
        if korean_chunks and english_chunks:
            avg_rank_kr = sum(c['rank'] for c in korean_chunks) / len(korean_chunks)
            avg_rank_en = sum(c['rank'] for c in english_chunks) / len(english_chunks)
            print(f"\n[언어 불일치 영향]")
            print(f"  한글 질문 시 한글 청크 평균 순위: {avg_rank_kr:.1f}위")
            print(f"  한글 질문 시 영어 청크 평균 순위: {avg_rank_en:.1f}위")
            if avg_rank_kr < avg_rank_en:
                print(f"  → 한글 청크가 {avg_rank_en - avg_rank_kr:.1f}위 더 높음 (언어 불일치가 원인일 가능성 높음)")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()





