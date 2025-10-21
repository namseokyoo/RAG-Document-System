import sys
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain


def main() -> None:
    app = QApplication(sys.argv)

    # QDarkStyle 적용 (선택)
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

    # 구성 로드 및 서비스 초기화
    config = ConfigManager().get_all()

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
    vectorstore = vector_manager.get_vectorstore()

    rag_chain = RAGChain(
        vectorstore=vectorstore,
        llm_api_type=config.get("llm_api_type", "request"),
        llm_base_url=config.get("llm_base_url", "http://localhost:11434"),
        llm_model=config.get("llm_model", "gemma3:4b"),
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.7),
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=config.get("reranker_initial_k", 20),
        # Query Expansion 설정
        enable_synonym_expansion=config.get("enable_synonym_expansion", True),
        enable_multi_query=config.get("enable_multi_query", True)
    )

    window = MainWindow(
        document_processor=doc_processor,
        vector_manager=vector_manager,
        rag_chain=rag_chain,
    )
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
