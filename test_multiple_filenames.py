"""여러 파일명 처리 로직 테스트 스크립트"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.rag_chain import RAGChain
from utils.vector_store import VectorStoreManager
from utils.document_processor import DocumentProcessor
from config import ConfigManager
import json

def load_config():
    """설정 파일 로드"""
    try:
        config_manager = ConfigManager()
        return config_manager.get_all()
    except Exception as e:
        print(f"❌ 설정 로드 실패: {e}")
        return None

def test_file_mention_extraction(rag_chain):
    """파일명 추출 테스트"""
    print("\n" + "="*60)
    print("📋 파일명 추출 테스트")
    print("="*60)
    
    test_cases = [
        ("@OLED연구.pdf에서 TADF 효율은?", ["OLED연구.pdf"]),
        ("@OLED연구.pdf와 @LED연구.pdf를 비교해줘", ["OLED연구.pdf", "LED연구.pdf"]),
        ("@파일.pdf에서 @파일.pdf의 내용은?", ["파일.pdf"]),  # 중복 제거
        ("@report.pdf와 @summary.pdf 그리고 @analysis.pdf를 분석해줘", ["report.pdf", "summary.pdf", "analysis.pdf"]),
        ("일반 질문입니다", []),
    ]
    
    for question, expected in test_cases:
        result = rag_chain._extract_all_file_mentions(question)
        status = "✅" if result == expected else "❌"
        print(f"{status} 질문: {question}")
        print(f"   예상: {expected}")
        print(f"   결과: {result}")
        if result != expected:
            print(f"   ⚠️  불일치!")
        print()

def test_filename_removal_and_translation(rag_chain):
    """파일명 제거 및 번역 테스트"""
    print("\n" + "="*60)
    print("📋 파일명 제거 및 번역 테스트")
    print("="*60)
    
    test_cases = [
        ("@OLED연구.pdf에서 TADF 효율은?", ["OLED연구.pdf"], "TADF 효율은?"),
        ("@OLED연구.pdf와 @LED연구.pdf를 비교해줘", ["OLED연구.pdf", "LED연구.pdf"], "를 비교해줘"),
        ("@파일.pdf에서 @파일.pdf의 내용은?", ["파일.pdf"], "의 내용은?"),
        ("@OLED연구.pdf", ["OLED연구.pdf"], ""),  # 파일명만 있는 경우
    ]
    
    for question, filenames, expected_remaining in test_cases:
        result = rag_chain._remove_filenames_and_translate(question, filenames)
        print(f"질문: {question}")
        print(f"제거할 파일명: {filenames}")
        print(f"예상 나머지: {expected_remaining}")
        print(f"번역 결과: {result}")
        print()

def test_single_file_mention(rag_chain):
    """단일 파일명 멘션 테스트"""
    print("\n" + "="*60)
    print("📋 단일 파일명 멘션 테스트")
    print("="*60)
    
    question = "@OLED연구.pdf에서 TADF 효율은?"
    print(f"질문: {question}")
    
    try:
        context = rag_chain._get_context(question)
        print(f"✅ 컨텍스트 획득 성공 (길이: {len(context)} 문자)")
        print(f"컨텍스트 미리보기: {context[:200]}...")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

def test_multiple_file_mentions(rag_chain):
    """여러 파일명 멘션 테스트"""
    print("\n" + "="*60)
    print("📋 여러 파일명 멘션 테스트")
    print("="*60)
    
    question = "@OLED연구.pdf와 @LED연구.pdf를 비교해줘"
    print(f"질문: {question}")
    
    try:
        context = rag_chain._get_context(question)
        print(f"✅ 컨텍스트 획득 성공 (길이: {len(context)} 문자)")
        print(f"컨텍스트 미리보기: {context[:200]}...")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

def test_intent_detection_multiple_files(rag_chain):
    """Intent Detection 여러 파일명 테스트"""
    print("\n" + "="*60)
    print("📋 Intent Detection 여러 파일명 테스트")
    print("="*60)
    
    question = "OLED연구.pdf와 LED연구.pdf를 비교해줘"
    print(f"질문: {question}")
    
    try:
        if hasattr(rag_chain, 'intent_detector') and rag_chain.intent_detector:
            all_filenames = rag_chain.intent_detector.extract_all_filenames(question)
            print(f"추출된 파일명: {all_filenames}")
            
            if all_filenames:
                translated = rag_chain._remove_filenames_and_translate(question, all_filenames)
                print(f"번역된 질문: {translated}")
        else:
            print("⚠️  Intent Detector가 초기화되지 않았습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

def main():
    """메인 테스트 함수"""
    print("="*60)
    print("🚀 여러 파일명 처리 로직 테스트 시작")
    print("="*60)
    
    # 설정 로드
    config = load_config()
    if not config:
        return
    
    # VectorStore 초기화
    print("\n📦 VectorStore 초기화 중...")
    vectorstore_manager = VectorStoreManager(
        persist_directory=config.get('persist_directory', 'data/chroma_db'),
        embedding_api_type=config.get('embedding_api_type', 'ollama'),
        embedding_base_url=config.get('embedding_base_url', 'http://localhost:11434'),
        embedding_model=config.get('embedding_model', 'mxbai-embed-large'),
        embedding_api_key=config.get('embedding_api_key', ''),
        shared_db_path=config.get('shared_db_path'),
        shared_db_enabled=config.get('shared_db_enabled', False),
        distance_function=config.get('chroma_distance_function', 'cosine')
    )
    
    # RAGChain 초기화
    print("🔧 RAGChain 초기화 중...")
    rag_chain = RAGChain(
        vectorstore=vectorstore_manager,
        llm_api_type=config.get('llm_api_type', 'ollama'),
        llm_base_url=config.get('llm_base_url', 'http://localhost:11434'),
        llm_model=config.get('llm_model', 'llama3'),
        llm_api_key=config.get('llm_api_key', ''),
        temperature=config.get('temperature', 0.3),
        enable_multi_query=config.get('enable_multi_query', True),
        multi_query_num=config.get('multi_query_num', 3),
        use_reranker=config.get('use_reranker', True),
        reranker_model=config.get('reranker_model', 'multilingual-mini'),
        enable_query_decomposition=config.get('enable_query_decomposition', True),
        enable_hyde=config.get('enable_hyde', True),
    )
    
    # 테스트 실행
    test_file_mention_extraction(rag_chain)
    test_filename_removal_and_translation(rag_chain)
    test_single_file_mention(rag_chain)
    test_multiple_file_mentions(rag_chain)
    test_intent_detection_multiple_files(rag_chain)
    
    print("\n" + "="*60)
    print("✅ 테스트 완료")
    print("="*60)

if __name__ == "__main__":
    main()

