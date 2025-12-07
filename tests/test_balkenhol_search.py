"""
Lennart Balkenhol 검색 테스트 및 진단
"""

import os
import sys
from pathlib import Path

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 환경 설정
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

print("=" * 80)
print("Lennart Balkenhol 검색 테스트")
print("=" * 80)

# Config 로드
config_manager = ConfigManager()
config = config_manager.get_all()

print(f"\n[1단계] 시스템 초기화")

# VectorStore 초기화
vector_manager = VectorStoreManager(
    persist_directory="data/chroma_db",
    embedding_api_type=config.get("embedding_api_type", "request"),
    embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
    embedding_model=config.get("embedding_model", "mxbai-embed-large:latest"),
    embedding_api_key=config.get("embedding_api_key", ""),
)
print(f"  - VectorStore 초기화 완료")

# RAGChain 초기화
rag_chain = RAGChain(
    vectorstore=vector_manager,
    llm_api_type=config.get("llm_api_type", "request"),
    llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
    llm_model=config.get("llm_model", "gemma3:latest"),
    llm_api_key=config.get("llm_api_key", ""),
    temperature=config.get("temperature", 0.3),
    top_k=config.get("top_k", 5),
    use_reranker=config.get("use_reranker", True),
    reranker_model=config.get("reranker_model", "multilingual-mini"),
    reranker_initial_k=config.get("reranker_initial_k", 30),
    enable_synonym_expansion=config.get("enable_synonym_expansion", False),
    enable_multi_query=config.get("enable_multi_query", True),
    multi_query_num=config.get("multi_query_num", 3),
    enable_hybrid_search=config.get("enable_hybrid_search", True),
    hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5),
    small_to_large_context_size=config.get("small_to_large_context_size", 800)
)
print(f"  - RAGChain 초기화 완료")

# DB 통계
collection = vector_manager.vectorstore._collection
total_chunks = collection.count()
print(f"  - DB 총 청크 수: {total_chunks:,}개")

# 테스트 질문
question = "Lennart Balkenhol"

print(f"\n{'=' * 80}")
print(f"[2단계] DB에서 직접 검색 (벡터 검색)")
print(f"{'=' * 80}")

# 벡터 검색
try:
    docs = vector_manager.search(question, k=10)
    print(f"\n검색 결과: {len(docs)}개 문서 발견")

    if docs:
        for i, doc in enumerate(docs, 1):
            content = doc.page_content[:200].replace('\n', ' ')
            metadata = doc.metadata
            file_name = metadata.get('file_name', 'N/A')
            page = metadata.get('page_number', 'N/A')
            score = metadata.get('score', 'N/A')

            print(f"\n{i}. [{file_name}] Page {page}")
            print(f"   Score: {score}")
            print(f"   Content: {content}...")
    else:
        print("  ⚠️ 검색 결과 없음")

except Exception as e:
    print(f"\n[오류] 벡터 검색 실패: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'=' * 80}")
print(f"[3단계] DB에서 키워드 검색 (텍스트 매칭)")
print(f"{'=' * 80}")

# ChromaDB에서 메타데이터 검색
try:
    # 모든 문서 가져오기
    all_data = collection.get(include=['metadatas', 'documents'])

    # "Balkenhol" 텍스트가 포함된 청크 찾기
    matching_chunks = []
    search_terms = ["Balkenhol", "balkenhol", "BALKENHOL", "Lennart", "lennart"]

    for i, (doc_id, doc_content, metadata) in enumerate(zip(
        all_data['ids'],
        all_data['documents'],
        all_data['metadatas']
    )):
        # 문서 내용에서 검색
        for term in search_terms:
            if term in doc_content:
                matching_chunks.append({
                    'id': doc_id,
                    'content': doc_content,
                    'metadata': metadata,
                    'matched_term': term
                })
                break

    print(f"\n키워드 매칭 결과: {len(matching_chunks)}개 청크 발견")

    if matching_chunks:
        for i, chunk in enumerate(matching_chunks[:5], 1):  # 최대 5개만 출력
            file_name = chunk['metadata'].get('file_name', 'N/A')
            page = chunk['metadata'].get('page_number', 'N/A')
            matched_term = chunk['matched_term']
            content_preview = chunk['content'][:300].replace('\n', ' ')

            print(f"\n{i}. [{file_name}] Page {page}")
            print(f"   매칭 키워드: {matched_term}")
            print(f"   Content: {content_preview}...")
    else:
        print("  ⚠️ 'Balkenhol' 또는 'Lennart'가 포함된 청크를 찾지 못했습니다.")
        print("  → 이 이름이 포함된 문서가 DB에 없을 수 있습니다.")

except Exception as e:
    print(f"\n[오류] 키워드 검색 실패: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'=' * 80}")
print(f"[4단계] RAG Chain 전체 테스트")
print(f"{'=' * 80}")

test_question = "Lennart Balkenhol 의 논문을 찾아야 오늘의 숙제가 해결돼?"

try:
    print(f"\n질문: {test_question}")
    print(f"\nRAG Chain 실행 중...")

    result = rag_chain.run(test_question)

    print(f"\n[응답]")
    print(f"  Answer: {result['answer'][:500]}")
    print(f"\n[검색된 문서]")
    print(f"  문서 수: {len(result.get('source_documents', []))}")

    for i, doc in enumerate(result.get('source_documents', [])[:3], 1):
        file_name = doc.metadata.get('file_name', 'N/A')
        page = doc.metadata.get('page_number', 'N/A')
        content_preview = doc.page_content[:150].replace('\n', ' ')

        print(f"\n  {i}. [{file_name}] Page {page}")
        print(f"     {content_preview}...")

except Exception as e:
    print(f"\n[오류] RAG Chain 실행 실패: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'=' * 80}")
print(f"[5단계] 문서 파일 직접 확인")
print(f"{'=' * 80}")

# PDF 파일에서 직접 검색
docs_dir = Path("data/embedded_documents")
pdf_files = list(docs_dir.glob("*.pdf"))

print(f"\nPDF 파일 수: {len(pdf_files)}개")
print(f"\n문서 목록:")
for i, pdf_file in enumerate(pdf_files, 1):
    file_size_mb = pdf_file.stat().st_size / 1024 / 1024
    print(f"  {i}. {pdf_file.name} ({file_size_mb:.1f} MB)")

# PyPDF2로 "Balkenhol" 검색
print(f"\n{'=' * 80}")
print(f"PDF 내용에서 'Balkenhol' 검색 중...")
print(f"{'=' * 80}")

try:
    import PyPDF2

    found_in_files = []

    for pdf_file in pdf_files:
        try:
            with open(pdf_file, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)

                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()

                    if "Balkenhol" in text or "balkenhol" in text or "Lennart" in text:
                        found_in_files.append({
                            'file': pdf_file.name,
                            'page': page_num,
                            'text_snippet': text[:500]
                        })
                        break  # 파일당 첫 번째 발견만
        except Exception as e:
            continue

    if found_in_files:
        print(f"\n✓ {len(found_in_files)}개 파일에서 발견!")
        for item in found_in_files[:3]:
            print(f"\n  파일: {item['file']}")
            print(f"  페이지: {item['page']}")
            print(f"  내용: {item['text_snippet'][:200].replace(chr(10), ' ')}...")
    else:
        print(f"\n⚠️ 어떤 PDF 파일에서도 'Balkenhol' 또는 'Lennart'를 찾지 못했습니다.")
        print(f"  → 이 이름이 포함된 논문이 다운로드되지 않았을 수 있습니다.")

except Exception as e:
    print(f"\n[오류] PDF 검색 실패: {e}")

print(f"\n{'=' * 80}")
print(f"진단 완료!")
print(f"{'=' * 80}")

print(f"\n[결론]")
if not matching_chunks and not found_in_files:
    print(f"  ⚠️ 'Lennart Balkenhol'이 포함된 문서가 DB에 없습니다.")
    print(f"  원인: 다운로드된 OLED 논문에 이 저자의 논문이 포함되지 않음")
    print(f"  해결: 해당 저자의 논문을 명시적으로 다운로드하여 추가 필요")
else:
    print(f"  ✓ 'Lennart Balkenhol'이 포함된 문서가 있습니다.")
    print(f"  문제: 벡터 검색 또는 RAG Chain 처리 과정의 이슈")
