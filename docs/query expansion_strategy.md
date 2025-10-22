3. RAG 검색 확장 전략 (Query Expansion)
📋 개요
이 문서는 RAG 시스템의 검색(Retrieval) 성능을 향상시키기 위한 3가지 주요 검색 확장 전략을 정의합니다. 사용자의 원본 쿼리가 문서 내의 어휘와 일치하지 않는 "어휘 불일치(Vocabulary Mismatch)" 문제를 해결하고, 쿼리의 문맥적 의도를 풍부하게 하여 검색 정확도와 재현율(Recall)을 극대화하는 것을 목표로 합니다.

⚙️ 핵심 인터페이스 (공통)
Python

# 모든 전략에서 공통으로 사용할 서비스 인터페이스
class LLMService:
    def generate(self, prompt_text, temperature=0.0):
        """LLM을 호출하여 텍스트 응답을 생성"""
        # (구현: OpenAI, Anthropic, Gemini API 등 호출)
        response = ...
        RETURN response.text

class VectorStore:
    def search(self, query_text, k=5):
        """텍스트 쿼리로 벡터 검색 수행"""
        # (구현: FAISS, Pinecone, ChromaDB 등)
        embedding = embedding_model.embed(query_text)
        results = ... # search by embedding
        RETURN results # (chunk_content, metadata, score) 리스트
    
    def search_by_embedding(self, query_embedding, k=5):
        """미리 계산된 임베딩으로 벡터 검색 수행"""
        results = ... 
        RETURN results
3.1. 전략 1: 동의어/연관어 확장 (Synonym/Related Term Expansion)
3.1.1. 개요
목표: 사용자의 원본 쿼리에 LLM이 생성한 동의어, 상/하위어, 관련 용어를 추가하여 검색 범위를 넓힙니다.

해결 문제: 사용자가 'PPT 청킹'이라고 검색했을 때, '파워포인트 분할'이라는 용어가 포함된 문서를 놓치는 문제.

작동 방식: 1 쿼리 -> LLM (동의어 생성) -> 1개의 확장된 쿼리 -> 1회 검색

3.1.2. 의사 코드 (Pseudocode)
Python

FUNCTION expand_query_with_synonyms(original_query, llm_service: LLMService):
    """
    LLM을 사용하여 원본 쿼리에 대한 동의어/연관어를 생성하고,
    이를 'OR' 조건으로 결합한 단일 확장 쿼리를 반환합니다.
    """
    
    # 1. LLM에 연관어 생성을 요청하는 프롬프트 정의
    prompt = f"""
    사용자의 검색 쿼리: "{original_query}"
    
    이 쿼리와 관련된 동의어 또는 밀접하게 연관된 검색 용어 3개를 생성해 줘.
    결과는 JSON 리스트 형식으로만 응답해 줘.
    예시: ["용어1", "용어2", "용어3"]
    """
    
    # 2. LLM 호출 및 결과 파싱
    try:
        response_text = llm_service.generate(prompt, temperature=0.0)
        related_terms = json.loads(response_text) # 예: ["파워포인트 분할", "PPT 슬라이드 처리"]
    except Exception as e:
        # LLM 실패 시 원본 쿼리만 사용
        print(f"동의어 확장 실패: {e}")
        related_terms = []

    # 3. 원본 쿼리와 연관어를 결합
    # (참고: 벡터 검색은 'OR'를 명시적으로 처리하지 않음. 
    # 대신, 풍부한 문맥의 '하나의 문장'으로 만드는 것이 더 효과적일 수 있음)
    
    # 전략 A: 단순 결합 (문맥 보강)
    expanded_query = original_query
    if related_terms:
        expanded_query += " (관련 용어: " + ", ".join(related_terms) + ")"
        
    # 전략 B: (검색엔진용) 'OR' 쿼리 (벡터 검색에는 부적합할 수 있음)
    # expanded_query = f"{original_query} OR {' OR '.join(related_terms)}"

    RETURN expanded_query # 예: "PPT 청킹 (관련 용어: 파워포인트 분할, PPT 슬라이드 처리)"

# --- RAG 파이프라인 적용 ---
FUNCTION main_rag_retrieval_stage(original_query, llm_service, vector_store):
    
    # 1. 쿼리 확장
    final_query = expand_query_with_synonyms(original_query, llm_service)
    
    print(f"원본 쿼리: {original_query}")
    print(f"확장 쿼리: {final_query}")
    
    # 2. 확장된 단일 쿼리로 1회 검색
    retrieved_chunks = vector_store.search(final_query, k=5)
    
    RETURN retrieved_chunks
3.2. 전략 2: 쿼리 재작성 (Multi-Query Rewriting)
3.2.1. 개요
목표: 사용자의 단일 쿼리를 LLM을 통해 여러 다른 관점의 **'대안 쿼리(Alternative Queries)'**로 재작성합니다.

해결 문제: 사용자의 쿼리가 너무 짧거나 모호할 때(예: '엑셀 RAG'), 다양한 가능성(구현, 전략, 문제점)을 탐색하여 검색 누락을 방지합니다.

작동 방식: 1 쿼리 -> LLM (3개의 대안 쿼리 생성) -> 3개의 개별 쿼리 -> 3회 검색 -> 결과 병합 및 재순위 매김

3.2.2. 의사 코드 (Pseudocode)
Python

FUNCTION generate_rewritten_queries(original_query, llm_service: LLMService, num_queries=3):
    """
    LLM을 사용하여 원본 쿼리를 여러 관점에서 재작성한 '대안 쿼리 리스트'를 생성합니다.
    """
    
    # 1. LLM에 쿼리 재작성을 요청하는 프롬프트 정의
    prompt = f"""
    당신은 사용자의 질문을 더 나은 검색 결과로 이끄는 전문 검색 엔지니어입니다.
    다음 원본 쿼리를 {num_queries}개의 서로 다른 관점에서 재작성해 주십시오.
    
    - 원본 쿼리는 그대로 유지하십시오.
    - 쿼리들은 서로 다른 접근 방식(예: 기술적 질문, 개념적 질문, 문제 해결)을 반영해야 합니다.
    
    원본 쿼리: "{original_query}"
    
    결과는 JSON 리스트 형식으로만 응답해 주십시오. 
    예시: ["쿼리1", "쿼리2", "쿼리3"]
    """
    
    # 2. LLM 호출 및 결과 파싱
    try:
        response_text = llm_service.generate(prompt, temperature=0.5) # 약간의 창의성 허용
        rewritten_queries = json.loads(response_text)
        
        # 원본 쿼리가 포함되지 않았다면, 리스트의 맨 앞에 추가
        if original_query not in rewritten_queries:
            rewritten_queries.insert(0, original_query)
            
    except Exception as e:
        print(f"쿼리 재작성 실패: {e}")
        rewritten_queries = [original_query] # 실패 시 원본만 사용

    RETURN rewritten_queries # 예: ["엑셀 RAG", "엑셀 파일을 RAG용으로 청킹하는 방법", "pandas로 xlsx 테이블을 처리하여 RAG에 넣기"]

# --- RAG 파이프라인 적용 ---
FUNCTION main_rag_retrieval_stage_multi_query(original_query, llm_service, vector_store, reranker_service):
    
    # 1. 여러 개의 대안 쿼리 생성
    queries_to_search = generate_rewritten_queries(original_query, llm_service, num_queries=3)
    
    print(f"검색할 쿼리들: {queries_to_search}")
    
    # 2. 모든 쿼리에 대해 병렬/순차적으로 검색 수행
    all_retrieved_chunks = []
    chunk_id_set = set()
    
    FOR query IN queries_to_search:
        # 각 쿼리마다 k개의 결과 검색
        results = vector_store.search(query, k=3)
        
        FOR chunk IN results:
            # 3. 중복 제거 (chunk_id 기준)
            if chunk.id not in chunk_id_set:
                all_retrieved_chunks.append(chunk)
                chunk_id_set.add(chunk.id)

    # 4. (필수) 재순위 매김 (Re-ranking)
    # 여러 쿼리에서 가져온 결과(수십 개)를 '원본 쿼리'와의 관련성을 기준으로 재정렬
    final_top_k_chunks = reranker_service.rerank(
        query=original_query, 
        chunks=all_retrieved_chunks,
        top_k=5
    )
    
    RETURN final_top_k_chunks
3.3. 전략 3: HyDE (Hypothetical Document Embeddings)
3.3.1. 개요
목표: 사용자의 '질문'으로 검색하는 대신, 그 질문에 대한 **'가상의 답변(Hypothetical Document)'**을 LLM으로 생성하고, 이 '가상 답변'의 임베딩으로 검색합니다.

해결 문제: '질문'과 '답변(문서 청크)'은 벡터 공간에서 거리가 멀 수 있습니다. 하지만 '답변'과 '답변'은 가깝습니다. 이 전략은 검색 대상을 '질문'에서 '답변'으로 바꾸어 일치율을 높입니다.

작동 방식: 1 쿼리 -> LLM (가상 답변 생성) -> 1개의 가상 답변 -> 가상 답변 임베딩 -> 1회 검색

3.3.2. 의사 코드 (Pseudocode)
Python

FUNCTION generate_hypothetical_document(original_query, llm_service: LLMService):
    """
    사용자의 쿼리(질문)에 대한 '가상의 답변'을 LLM으로 생성합니다.
    이 답변은 사실이 아닐 수도 있지만, 검색에 사용될 '풍부한 문맥'을 제공합니다.
    """
    
    # 1. LLM에 가상 답변 생성을 요청하는 프롬프트 정의
    prompt = f"""
    다음 질문에 대한 이상적이고 상세한 답변을 작성해 주십시오.
    이 답변은 사실에 기반할 필요는 없으며, 오직 벡터 검색(Vector Search)의 정확도를 높이기 위한 '가상의 문서(Hypothetical Document)'로만 사용됩니다.
    
    질문: "{original_query}"
    
    가상의 답변:
    """
    
    # 2. LLM 호출 (약간의 창의성 허용)
    try:
        hypothetical_doc = llm_service.generate(prompt, temperature=0.4)
    except Exception as e:
        print(f"HyDE 생성 실패: {e}")
        # HyDE 실패 시, 검색 전략을 원본 쿼리 검색으로 되돌려야 함
        RETURN None

    RETURN hypothetical_doc

# --- RAG 파이프라인 적용 ---
FUNCTION main_rag_retrieval_stage_hyde(original_query, llm_service, vector_store, embedding_model):
    
    # 1. 가상의 답변 생성
    hypothetical_doc = generate_hypothetical_document(original_query, llm_service)
    
    IF hypothetical_doc IS None:
        # HyDE 실패 시, 표준 검색으로 Fallback
        print("HyDE 실패. 표준 검색으로 Fallback.")
        retrieved_chunks = vector_store.search(original_query, k=5)
        RETURN retrieved_chunks

    print(f"HyDE 생성됨 (일부): {hypothetical_doc[:100]}...")

    # 2. (핵심) 원본 쿼리가 아닌, '가상 답변'을 임베딩
    query_embedding = embedding_model.embed(hypothetical_doc)
    
    # 3. 가상 답변의 임베딩을 사용하여 벡터 검색 수행
    retrieved_chunks = vector_store.search_by_embedding(query_embedding, k=5)
    
    # 4. 검색된 청크 반환
    # (참고: 이 청크들은 최종 LLM에 '원본 쿼리'와 함께 전달됨)
    RETURN retrieved_chunks