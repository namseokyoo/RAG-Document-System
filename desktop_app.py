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
        config_manager = ConfigManager()
        config = config_manager.get_all()

        # reranker_model 검증 (multilingual-mini만 지원)
        reranker_model = config.get("reranker_model", "multilingual-mini")
        if reranker_model != "multilingual-mini":
            show_error_dialog(
                "설정 오류",
                f"지원하지 않는 reranker_model: {reranker_model}",
                "config.json 파일에서 reranker_model을 'multilingual-mini'로 변경하세요.\n\n"
                f"현재 설정: {reranker_model}\n"
                f"권장 설정: multilingual-mini"
            )
            sys.exit(1)

        # 공유 DB 설정 로드 (config.json에서 직접 읽기)
        shared_db_enabled = config.get("shared_db_enabled", False)
        shared_db_path = config.get("shared_db_path", "")

        # 공유 DB 경로 유효성 검증
        if shared_db_enabled and shared_db_path:
            import os
            chroma_db_file = os.path.join(shared_db_path, "chroma.sqlite3")
            if os.path.exists(chroma_db_file):
                print(f"[초기화] ✓ 공유 DB 연결 성공: {shared_db_path}")
            else:
                print(f"[초기화] ⚠ 공유 DB 경로에 chroma.sqlite3 파일이 없습니다: {shared_db_path}")
                print(f"[초기화] ℹ 설정 탭에서 올바른 경로를 지정하세요")
                shared_db_enabled = False
        elif shared_db_enabled:
            print(f"[초기화] ⚠ 공유 DB 사용이 활성화되었지만 경로가 설정되지 않았습니다")
            print(f"[초기화] ℹ 설정 탭에서 공유 DB 경로를 지정하세요")
            shared_db_enabled = False
        else:
            print(f"[초기화] ℹ 공유 DB 사용 안 함 (개인 DB만 사용)")

        doc_processor = DocumentProcessor(
            chunk_size=config.get("chunk_size", 1500),
            chunk_overlap=config.get("chunk_overlap", 200),
        )

        vector_manager = VectorStoreManager(
            persist_directory="data/chroma_db",
            embedding_api_type=config.get("embedding_api_type", "ollama"),
            embedding_base_url=config.get("embedding_base_url", "http://localhost:11434"),
            embedding_model=config.get("embedding_model", "nomic-embed-text"),
            embedding_api_key=config.get("embedding_api_key", ""),
            shared_db_path=shared_db_path if shared_db_enabled else None,
            shared_db_enabled=shared_db_enabled,
            distance_function=config.get("chroma_distance_function", "l2"),
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
            hybrid_bm25_weight=config.get("hybrid_bm25_weight", 0.5),
            # Small-to-Large 설정
            small_to_large_context_size=config.get("small_to_large_context_size", 800)
        )

        # Score-based Filtering 설정 (OpenAI 스타일)
        if config.get("enable_score_filtering", True):
            rag_chain.enable_score_filtering = True
            rag_chain.score_threshold = config.get("reranker_score_threshold", 0.5)
            rag_chain.max_num_results = config.get("max_num_results", 20)
            rag_chain.min_num_results = config.get("min_num_results", 3)
            rag_chain.enable_adaptive_threshold = config.get("enable_adaptive_threshold", True)
            rag_chain.adaptive_threshold_percentile = config.get("adaptive_threshold_percentile", 0.6)
            print(f"[CONFIG] Score-based Filtering: threshold={rag_chain.score_threshold}, max={rag_chain.max_num_results}, adaptive={rag_chain.enable_adaptive_threshold}")

        # Exhaustive Retrieval 설정 (대량 문서 처리)
        if config.get("enable_exhaustive_retrieval", True):
            rag_chain.enable_exhaustive_retrieval = True
            rag_chain.exhaustive_max_results = config.get("exhaustive_max_results", 100)
            rag_chain.enable_single_file_optimization = config.get("enable_single_file_optimization", True)
            print(f"[CONFIG] Exhaustive Retrieval: max={rag_chain.exhaustive_max_results}, single_file={rag_chain.enable_single_file_optimization}")

        # Question Classifier 설정 (Phase 2: Quick Wins)
        enable_classifier = config.get("enable_question_classifier", True)
        if enable_classifier:
            # 분류기는 RAGChain.__init__에서 자동 초기화됨
            # verbose 설정만 조정
            if hasattr(rag_chain, 'question_classifier') and rag_chain.question_classifier:
                rag_chain.question_classifier.verbose = config.get("classifier_verbose", False)
                classifier_use_llm = config.get("classifier_use_llm", True)
                rag_chain.question_classifier.use_llm_fallback = classifier_use_llm and (rag_chain.question_classifier.llm is not None)
                print(f"[CONFIG] Question Classifier: enabled=True, use_llm={classifier_use_llm}, verbose={config.get('classifier_verbose', False)}")
        else:
            # 분류기 비활성화
            if hasattr(rag_chain, 'question_classifier'):
                rag_chain.question_classifier = None
                print(f"[CONFIG] Question Classifier: disabled")

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
                "지원되는 모델: 'multilingual-mini'"
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
