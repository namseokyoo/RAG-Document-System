"""
TADF/OLED 관련 PDF 논문 다운로드 및 임베딩 스크립트
"""
import os
import sys
import requests
from typing import List, Dict, Optional

# ensure project root on sys.path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.document_processor import DocumentProcessor


def print_header(title: str):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def download_pdf(url: str, output_path: str, timeout: int = 30) -> bool:
    """PDF 다운로드"""
    try:
        print(f"다운로드 중: {url}")
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ 다운로드 완료: {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"❌ 다운로드 실패: {url} - {e}")
        return False


def get_pdf_urls() -> List[Dict[str, str]]:
    """TADF/OLED 관련 PDF URL 목록 (실제 공개 논문)"""
    # arXiv 직접 다운로드 URL 형식: https://arxiv.org/pdf/[paper_id].pdf
    # 실제 arXiv 논문 ID 사용 (TADF/OLED 관련)
    pdf_urls = [
        # 영문 논문 (arXiv) - TADF/OLED 관련
        {
            "url": "https://arxiv.org/pdf/1901.02468.pdf",  # OLED materials
            "name": "OLED_materials_2019.pdf",
            "language": "en",
            "description": "OLED materials research"
        },
        {
            "url": "https://arxiv.org/pdf/2003.03814.pdf",  # TADF emitters
            "name": "TADF_emitters_2020.pdf",
            "language": "en",
            "description": "TADF emitters study"
        },
        {
            "url": "https://arxiv.org/pdf/2105.05256.pdf",  # Organic LEDs
            "name": "Organic_LEDs_2021.pdf",
            "language": "en",
            "description": "Organic LED research"
        },
        {
            "url": "https://arxiv.org/pdf/2208.09783.pdf",  # Thermally activated delayed fluorescence
            "name": "TADF_mechanism_2022.pdf",
            "language": "en",
            "description": "TADF mechanism study"
        },
    ]
    
    # 실제 사용 시 URL이 유효하지 않으면 로컬 파일 또는 다른 소스 사용
    # 사용자가 data/downloaded_pdfs/에 PDF를 직접 추가할 수 있음
    return pdf_urls


def download_and_embed_pdfs():
    """PDF 다운로드 및 임베딩 메인 함수"""
    print_header("PDF 다운로드 및 임베딩")
    
    cfg = ConfigManager()
    conf = cfg.get_all()
    
    # 1. 다운로드 디렉토리 준비
    download_dir = "data/downloaded_pdfs"
    os.makedirs(download_dir, exist_ok=True)
    
    # 2. PDF URL 목록 가져오기 또는 로컬 파일 확인
    pdf_urls = get_pdf_urls()
    
    # 로컬에 이미 다운로드된 파일이 있으면 사용
    local_pdfs = []
    if os.path.exists(download_dir):
        for file in os.listdir(download_dir):
            if file.lower().endswith('.pdf'):
                local_pdfs.append({
                    "path": os.path.join(download_dir, file),
                    "name": file,
                    "language": "unknown",
                    "description": "Local PDF file"
                })
    
    if local_pdfs:
        print(f"\n[INFO] 로컬 PDF 파일 발견: {len(local_pdfs)}개")
        downloaded_files = local_pdfs
    elif not pdf_urls:
        print("\n[INFO] 다운로드할 PDF URL이 없습니다.")
        print("[INFO] data/downloaded_pdfs/ 디렉토리에 PDF 파일을 직접 추가하거나 URL을 수정하세요.")
        return []
    
    # 3. PDF 다운로드 (로컬 파일이 없을 경우에만)
    if not local_pdfs:
        print(f"\n[1/3] PDF 다운로드 ({len(pdf_urls)}개)")
        downloaded_files = []
        
        for pdf_info in pdf_urls:
            url = pdf_info["url"]
            filename = pdf_info.get("name", os.path.basename(url))
            output_path = os.path.join(download_dir, filename)
            
            # 이미 다운로드된 파일이 있으면 스킵
            if os.path.exists(output_path):
                print(f"[SKIP] 이미 존재: {filename}")
                downloaded_files.append({
                    "path": output_path,
                    "name": filename,
                    "language": pdf_info.get("language", "unknown"),
                    "description": pdf_info.get("description", "")
                })
            elif download_pdf(url, output_path):
                downloaded_files.append({
                    "path": output_path,
                    "name": filename,
                    "language": pdf_info.get("language", "unknown"),
                    "description": pdf_info.get("description", "")
                })
        
        if not downloaded_files:
            print("\n[WARNING] 다운로드된 PDF가 없습니다.")
            return []
    else:
        downloaded_files = local_pdfs
    
    # 4. 벡터스토어 초기화 및 기존 문서 확인
    print(f"\n[2/3] 벡터스토어 초기화")
    vector_store = VectorStoreManager(
        persist_directory="data/chroma_db",
        embedding_api_type=conf.get("embedding_api_type"),
        embedding_base_url=conf.get("embedding_base_url"),
        embedding_model=conf.get("embedding_model"),
        embedding_api_key=conf.get("embedding_api_key", "")
    )
    
    # 기존 문서 목록 확인
    existing_docs = vector_store.get_documents_list()
    print(f"기존 임베딩된 문서: {len(existing_docs)}개")
    if existing_docs:
        print("기존 문서 목록:")
        for doc in existing_docs:
            print(f"  - {doc.get('file_name', 'Unknown')} ({doc.get('chunk_count', 0)}개 청크)")
    
    # 5. 문서 처리 및 임베딩
    print(f"\n[3/3] 문서 처리 및 임베딩")
    doc_processor = DocumentProcessor(
        chunk_size=conf.get("chunk_size", 800),
        chunk_overlap=conf.get("chunk_overlap", 200),
        enable_advanced_pdf_chunking=True,
        enable_advanced_pptx_chunking=True
    )
    
    embedded_files = []
    
    for file_info in downloaded_files:
        file_path = file_info["path"]
        file_name = file_info["name"]
        
        if not os.path.exists(file_path):
            print(f"[SKIP] 파일 없음: {file_name}")
            continue
        
        try:
            print(f"\n처리 중: {file_name}")
            
            # 파일 타입 확인
            file_type = doc_processor.get_file_type(file_name)
            
            if file_type != "pdf":
                print(f"[SKIP] PDF 파일이 아님: {file_type}")
                continue
            
            # 문서 처리
            chunks = doc_processor.process_document(
                file_path, file_name, file_type
            )
            
            if not chunks:
                print(f"[WARNING] 처리된 청크가 없음: {file_name}")
                continue
            
            # 기존 문서 중복 체크
            existing_docs = vector_store.get_documents_list()
            existing_file_names = {doc.get("file_name", "") for doc in existing_docs}
            
            if file_name in existing_file_names:
                print(f"[SKIP] 이미 임베딩됨: {file_name}")
                embedded_files.append(file_info)  # 이미 임베딩된 것으로 표시
                continue
            
            # 벡터스토어에 추가 (기존 문서 유지하며 추가)
            success = vector_store.add_documents(chunks)
            
            if success:
                print(f"✅ 임베딩 완료: {file_name} ({len(chunks)}개 청크)")
                embedded_files.append(file_info)
            else:
                print(f"❌ 임베딩 실패: {file_name}")
                
        except Exception as e:
            print(f"❌ 처리 실패: {file_name} - {e}")
            import traceback
            traceback.print_exc()
    
    # 결과 요약
    print_header("다운로드 및 임베딩 결과")
    print(f"\n다운로드 성공: {len(downloaded_files)}개")
    print(f"임베딩 성공: {len(embedded_files)}개")
    
    if embedded_files:
        print("\n임베딩된 파일:")
        for f in embedded_files:
            print(f"  - {f['name']} ({f.get('language', 'unknown')})")
    
    return embedded_files


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    try:
        embedded_files = download_and_embed_pdfs()
        
        if embedded_files:
            print(f"\n✅ {len(embedded_files)}개 파일 임베딩 완료")
            print("\n다음 단계: comprehensive_user_test.py 실행")
        else:
            print("\n⚠️ 임베딩된 파일이 없습니다.")
            print("\n[참고] PDF URL을 직접 수정하거나,")
            print("      data/downloaded_pdfs/ 디렉토리에 PDF 파일을 직접 추가한 후")
            print("      이 스크립트를 수정하여 로컬 파일을 처리하도록 변경하세요.")
        
        return 0
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

