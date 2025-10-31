"""
개선된 청킹 전략 테스트 및 검증 스크립트
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
from utils.document_processor import DocumentProcessor
from utils.pdf_chunking_engine import PDFChunkingEngine
import json


def print_header(title: str):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def test_improved_chunking(pdf_path: str):
    """개선된 청킹 전략 테스트"""
    print_header("개선된 청킹 전략 테스트 시작")
    
    cfg = ConfigManager()
    conf = cfg.get_all()
    
    # 1. 문서 처리기 초기화 (개선된 설정 적용)
    print("\n[1/4] 문서 처리기 초기화 (개선된 청킹 전략)")
    doc_processor = DocumentProcessor(
        chunk_size=conf.get("chunk_size", 800),
        chunk_overlap=conf.get("chunk_overlap", 200),
        enable_advanced_pdf_chunking=True,
        enable_advanced_pptx_chunking=True
    )
    
    # 2. PDF 청킹 테스트 (벡터스토어에 추가하지 않고 청크만 생성)
    print(f"\n[2/4] PDF 청킹 테스트: {pdf_path}")
    print("-" * 60)
    
    try:
        # 파일 타입 확인
        file_name = os.path.basename(pdf_path)
        file_type = doc_processor.get_file_type(file_name)
        
        if file_type != "pdf":
            print(f"[ERROR] PDF 파일이 아닙니다: {file_type}")
            return
        
        # 직접 PDF 청킹 엔진 사용하여 청크 생성
        pdf_config = {
            "max_size": conf.get("chunk_size", 800),
            "overlap_size": conf.get("chunk_overlap", 200),
            "min_chunk_size": 50,  # 개선된 최소 길이
            "min_word_count": 5,   # 개선된 최소 단어 수
            "enable_small_to_large": True,
            "enable_layout_analysis": True
        }
        
        pdf_engine = PDFChunkingEngine(pdf_config)
        chunks = pdf_engine.process_pdf_document(pdf_path)
        
        print(f"생성된 청크 수: {len(chunks)}")
        
        # 3. 청크 품질 분석
        print_header("[3/4] 청크 품질 분석")
        
        # 통계 수집
        total_chunks = len(chunks)
        short_chunks = []  # 50자 미만
        very_short_chunks = []  # 10자 미만
        single_char_chunks = []  # 단일 문자
        empty_chunks = []  # 빈 청크
        
        chunk_lengths = []
        
        for chunk in chunks:
            content = chunk.content
            length = len(content.strip())
            chunk_lengths.append(length)
            
            # 짧은 청크 분류
            if length < 50:
                short_chunks.append((chunk.id, length, content[:50]))
            if length < 10:
                very_short_chunks.append((chunk.id, length, content))
            if length == 1:
                single_char_chunks.append((chunk.id, content))
            if length == 0:
                empty_chunks.append(chunk.id)
        
        # 통계 출력
        if chunk_lengths:
            avg_length = sum(chunk_lengths) / len(chunk_lengths)
            min_length = min(chunk_lengths)
            max_length = max(chunk_lengths)
            
            print(f"\n청크 길이 통계:")
            print(f"  평균: {avg_length:.1f}자")
            print(f"  최소: {min_length}자")
            print(f"  최대: {max_length}자")
            
            # 길이 분포
            short_count = sum(1 for l in chunk_lengths if l < 50)
            medium_count = sum(1 for l in chunk_lengths if 50 <= l < 200)
            long_count = sum(1 for l in chunk_lengths if l >= 200)
            
            print(f"\n청크 길이 분포:")
            print(f"  짧음 (< 50자): {short_count}개 ({short_count/total_chunks*100:.1f}%)")
            print(f"  보통 (50-200자): {medium_count}개 ({medium_count/total_chunks*100:.1f}%)")
            print(f"  길음 (>= 200자): {long_count}개 ({long_count/total_chunks*100:.1f}%)")
        
        # 문제 청크 리포트
        print(f"\n문제 청크 리포트:")
        if very_short_chunks:
            print(f"  [WARNING] 매우 짧은 청크 (10자 미만): {len(very_short_chunks)}개")
            print("  샘플:")
            for chunk_id, length, content in very_short_chunks[:5]:
                print(f"    - ID: {chunk_id[:20]}... | 길이: {length}자 | 내용: {repr(content)}")
        else:
            print(f"  [OK] 매우 짧은 청크 없음")
        
        if single_char_chunks:
            print(f"  [WARNING] 단일 문자 청크: {len(single_char_chunks)}개")
            print("  샘플:")
            for chunk_id, content in single_char_chunks[:5]:
                print(f"    - ID: {chunk_id[:20]}... | 내용: {repr(content)}")
        else:
            print(f"  [OK] 단일 문자 청크 없음")
        
        if empty_chunks:
            print(f"  [WARNING] 빈 청크: {len(empty_chunks)}개")
        else:
            print(f"  [OK] 빈 청크 없음")
        
        # 개선 효과 평가
        print_header("[4/4] 개선 효과 평가")
        
        improvement_score = 0
        max_score = 100
        
        # 매우 짧은 청크 비율 (0%면 30점)
        if total_chunks > 0:
            very_short_ratio = len(very_short_chunks) / total_chunks
            very_short_score = max(0, 30 - int(very_short_ratio * 3000))
            improvement_score += very_short_score
            print(f"1. 매우 짧은 청크 비율: {very_short_ratio*100:.2f}% → {very_short_score}/30점")
        
        # 단일 문자 청크 비율 (0%면 30점)
        if total_chunks > 0:
            single_char_ratio = len(single_char_chunks) / total_chunks
            single_char_score = max(0, 30 - int(single_char_ratio * 3000))
            improvement_score += single_char_score
            print(f"2. 단일 문자 청크 비율: {single_char_ratio*100:.2f}% → {single_char_score}/30점")
        
        # 빈 청크 비율 (0%면 20점)
        if total_chunks > 0:
            empty_ratio = len(empty_chunks) / total_chunks
            empty_score = max(0, 20 - int(empty_ratio * 2000))
            improvement_score += empty_score
            print(f"3. 빈 청크 비율: {empty_ratio*100:.2f}% → {empty_score}/20점")
        
        # 평균 길이 점수 (100자 이상이면 20점)
        if chunk_lengths:
            avg_length_score = min(20, int(avg_length / 5))
            improvement_score += avg_length_score
            print(f"4. 평균 청크 길이: {avg_length:.1f}자 → {avg_length_score}/20점")
        
        print(f"\n종합 개선 점수: {improvement_score}/100점")
        
        if improvement_score >= 90:
            print("[SUCCESS] 청킹 전략이 우수합니다!")
        elif improvement_score >= 70:
            print("[GOOD] 청킹 전략이 양호합니다.")
        else:
            print("[WARNING] 추가 개선이 필요합니다.")
        
        return {
            "total_chunks": total_chunks,
            "very_short_chunks": len(very_short_chunks),
            "single_char_chunks": len(single_char_chunks),
            "empty_chunks": len(empty_chunks),
            "avg_length": avg_length if chunk_lengths else 0,
            "improvement_score": improvement_score
        }
        
    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_rechunk_document(pdf_path: str, persist_dir: str = "data/chroma_db"):
    """기존 문서를 재청킹하여 벡터스토어에 추가"""
    print_header("기존 문서 재청킹 테스트")
    
    cfg = ConfigManager()
    conf = cfg.get_all()
    
    try:
        # 1. 벡터스토어 초기화
        print("\n[1/3] 벡터스토어 초기화")
        vector_store = VectorStoreManager(
            persist_directory=persist_dir,
            embedding_api_type=conf.get("embedding_api_type"),
            embedding_base_url=conf.get("embedding_base_url"),
            embedding_model=conf.get("embedding_model"),
            embedding_api_key=conf.get("embedding_api_key", "")
        )
        
        # 2. 기존 문서 삭제 (선택적)
        file_name = os.path.basename(pdf_path)
        print(f"\n[2/3] 기존 문서 삭제: {file_name}")
        
        try:
            if vector_store.delete_document(file_name):
                print(f"[OK] 기존 문서 삭제 완료: {file_name}")
            else:
                print(f"[INFO] 기존 문서 없음: {file_name}")
        except Exception as e:
            print(f"[WARNING] 문서 삭제 실패 (무시): {e}")
        
        # 3. 개선된 청킹으로 문서 재처리 및 추가
        print(f"\n[3/3] 개선된 청킹으로 문서 재처리")
        print("-" * 60)
        
        doc_processor = DocumentProcessor(
            chunk_size=conf.get("chunk_size", 800),
            chunk_overlap=conf.get("chunk_overlap", 200),
            enable_advanced_pdf_chunking=True,
            enable_advanced_pptx_chunking=True
        )
        
        # 문서 처리
        file_type = doc_processor.get_file_type(file_name)
        chunks = doc_processor.process_document(
            pdf_path, file_name, file_type
        )
        
        print(f"처리된 청크 수: {len(chunks)}")
        
        # 벡터스토어에 추가
        if chunks:
            success = vector_store.add_documents(chunks)
            if success:
                print(f"[OK] 문서 추가 완료: {file_name} ({len(chunks)}개 청크)")
                
                # 재청킹 후 통계
                print("\n재청킹 후 통계:")
                stats = {
                    "total_chunks": len(chunks),
                    "avg_length": sum(len(c.page_content) for c in chunks) / len(chunks) if chunks else 0,
                    "short_chunks": sum(1 for c in chunks if len(c.page_content) < 50),
                    "empty_chunks": sum(1 for c in chunks if not c.page_content.strip())
                }
                
                print(f"  총 청크 수: {stats['total_chunks']}")
                print(f"  평균 길이: {stats['avg_length']:.1f}자")
                print(f"  짧은 청크 (< 50자): {stats['short_chunks']}개")
                print(f"  빈 청크: {stats['empty_chunks']}개")
                
                return True
            else:
                print(f"[ERROR] 문서 추가 실패: {file_name}")
                return False
        else:
            print(f"[WARNING] 처리된 청크가 없습니다: {file_name}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 재청킹 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 100)
    print("개선된 청킹 전략 종합 테스트")
    print("=" * 100)
    
    # 테스트할 PDF 파일 찾기
    pdf_file = "s41566-024-01395-1 (1).pdf"
    
    if not os.path.exists(pdf_file):
        print(f"[ERROR] PDF 파일을 찾을 수 없습니다: {pdf_file}")
        print("현재 디렉토리:", os.getcwd())
        return
    
    # 1. 개선된 청킹 전략 테스트 (벡터스토어 미사용)
    print("\n" + "=" * 100)
    print("STEP 1: 개선된 청킹 전략 테스트 (청크 생성만)")
    print("=" * 100)
    test_result = test_improved_chunking(pdf_file)
    
    # 2. 재청킹 테스트 (벡터스토어에 추가)
    print("\n" + "=" * 100)
    print("STEP 2: 기존 문서 재청킹 (벡터스토어에 추가)")
    print("=" * 100)
    rechunk_result = test_rechunk_document(pdf_file)
    
    # 최종 요약
    print_header("최종 요약")
    print("\n테스트 결과:")
    if test_result:
        print(f"  청킹 품질 점수: {test_result['improvement_score']}/100점")
        print(f"  총 청크 수: {test_result['total_chunks']}")
        print(f"  매우 짧은 청크: {test_result['very_short_chunks']}개")
        print(f"  단일 문자 청크: {test_result['single_char_chunks']}개")
        print(f"  평균 길이: {test_result['avg_length']:.1f}자")
    
    if rechunk_result:
        print(f"  재청킹 성공: {pdf_file}")
    else:
        print(f"  재청킹 실패 또는 스킵")
    
    print("\n테스트 완료!")


if __name__ == "__main__":
    main()

