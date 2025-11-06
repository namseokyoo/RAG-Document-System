import sys
import os

# Windows 콘솔 UTF-8 인코딩 설정 (이모지 출력 오류 방지)
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow
from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain

# 오프라인 모드 설정 (외부 네트워크 의존성 제거)
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

# 폐쇄망 환경에서 tiktoken 오류 방지
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
# OpenAI API는 공식 엔드포인트를 사용하므로 환경변수 설정하지 않음
# os.environ["OPENAI_API_BASE"] = "http://localhost:11434"  # 제거됨 - OpenAI 타입 사용 시 문제 발생

# ChromaDB 텔레메트리 비활성화 (폐쇄망 환경)
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

# PyTorch Hub 비활성화 (폐쇄망 환경)
os.environ["TORCH_HOME"] = "./torch_cache"
os.environ["HF_HOME"] = "./huggingface_cache"

# 추가 오프라인 모드 설정
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # 경고 메시지 방지
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"  # 사용자 경고 무시


def show_error_dialog(title: str, message: str, details: str = "") -> None:
    """에러 다이얼로그 표시"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    if details:
        msg.setDetailedText(details)
    msg.exec()


def main() -> None:
    app = QApplication(sys.argv)

    try:
        import qdarkstyle
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyside6"))
    except Exception:
        pass

    # 아이콘 (선택)
    try:
        app.setWindowIcon(QIcon("resources/icons/app.png"))
    except Exception:
        pass

    try:
        # 구성 로드 및 서비스 초기화
        config = ConfigManager().get_all()
        
        # reranker_model 검증
        reranker_model = config.get("reranker_model", "multilingual-mini")
        if reranker_model == "korean":
            show_error_dialog(
                "설정 오류",
                "reranker_model이 'korean'으로 설정되어 있습니다.",
                "config.json 파일에서 reranker_model을 'multilingual-mini' 또는 'multilingual-base'로 변경하세요.\n\n"
                "korean 모델은 더 이상 지원되지 않습니다."
            )
            sys.exit(1)
        
        if reranker_model not in ["multilingual-mini", "multilingual-base"]:
            show_error_dialog(
                "설정 오류",
                f"지원하지 않는 reranker_model: {reranker_model}",
                "config.json 파일에서 reranker_model을 'multilingual-mini' 또는 'multilingual-base'로 변경하세요."
            )
            sys.exit(1)

        doc_processor = DocumentProcessor(
            chunk_size=config.get("chunk_size", 500),
            chunk_overlap=config.get("chunk_overlap", 100),
        )

        vector_manager = VectorStoreManager(
            persist_directory="data/chroma_db",
            embedding_api_type=config.get("embedding_api_type", "ollama"),
            embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
            embedding_model=config.get("embedding_model", "nomic-embed-text"),
            embedding_api_key=config.get("embedding_api_key", ""),
        )
        # VectorStoreManager 객체를 RAGChain에 전달 (Chroma 객체 직접 전달하지 않음)
        multi_query_num = int(config.get("multi_query_num", 3))
        enable_multi_query = config.get("enable_multi_query", True) and multi_query_num > 0

        rag_chain = RAGChain(
            vectorstore=vector_manager,  # VectorStoreManager 객체 전달
            llm_api_type=config.get("llm_api_type", "request"),
            llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
            llm_model=config.get("llm_model", "gemma3:4b"),
            llm_api_key=config.get("llm_api_key", ""),
            temperature=config.get("temperature", 0.7),
            top_k=config.get("top_k", 3),
            use_reranker=config.get("use_reranker", True),
            reranker_model=reranker_model,
            reranker_initial_k=config.get("reranker_initial_k", 20),
            # Query Expansion 설정
            enable_synonym_expansion=config.get("enable_synonym_expansion", True),
            enable_multi_query=enable_multi_query,
            multi_query_num=multi_query_num,
            # Phase 4: Hybrid Search (BM25 + Vector)
            enable_hybrid_search=config.get("enable_hybrid_search", True),
            hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5)
        )

        window = MainWindow(
            document_processor=doc_processor,
            vector_manager=vector_manager,
            rag_chain=rag_chain,
        )
        window.show()

        sys.exit(app.exec())
        
    except ValueError as e:
        error_msg = str(e)
        if "reranker" in error_msg.lower() or "korean" in error_msg.lower():
            show_error_dialog(
                "Reranker 모델 오류",
                "Reranker 모델 설정에 문제가 있습니다.",
                f"오류 내용: {error_msg}\n\n"
                "config.json 파일에서 reranker_model을 확인하세요.\n"
                "지원되는 모델: 'multilingual-mini', 'multilingual-base'"
            )
        else:
            show_error_dialog(
                "초기화 오류",
                "프로그램 초기화 중 오류가 발생했습니다.",
                f"오류 내용: {error_msg}"
            )
        sys.exit(1)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        show_error_dialog(
            "프로그램 구동 오류",
            "프로그램을 시작하는 중 오류가 발생했습니다.",
            f"오류 내용: {str(e)}\n\n상세 정보:\n{error_details}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
