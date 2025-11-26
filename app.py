import streamlit as st
import os
from datetime import datetime
import uuid

# 오프라인 모드 설정 (외부 네트워크 의존성 제거)
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

# 폐쇄망 환경에서 tiktoken 오류 방지
os.environ["TIKTOKEN_CACHE_DIR"] = "./tiktoken_cache"
os.environ["OPENAI_API_BASE"] = "http://localhost:11434"

# ChromaDB 텔레메트리 비활성화 (폐쇄망 환경)
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

# PyTorch Hub 비활성화 (폐쇄망 환경)
os.environ["TORCH_HOME"] = "./torch_cache"
os.environ["HF_HOME"] = "./huggingface_cache"

# 추가 오프라인 모드 설정
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # 경고 메시지 방지
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"  # 사용자 경고 무시

from config import ConfigManager
from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
from utils.chat_history import ChatHistoryManager

# 페이지 설정
st.set_page_config(
    page_title="RAG 시스템 - Ollama",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 전역 스타일 설정
st.markdown("""
<style>
    /* 전체 글자 크기 15% 축소 */
    html, body, [class*="css"] {
        font-size: 85% !important;
    }
    
    /* 제목 크기 조정 */
    h1 { font-size: 1.7rem !important; }
    h2 { font-size: 1.4rem !important; }
    h3 { font-size: 1.2rem !important; }
    
    /* 세션 리스트 간격 줄이기 */
    .stDivider {
        margin: 0.3rem 0 !important;
    }
    
    /* 버튼 텍스트 크기 */
    .stButton button {
        font-size: 0.85rem !important;
    }
    
    /* 캡션 크기 */
    .caption {
        font-size: 0.75rem !important;
    }
    
    /* 입력 필드 */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        font-size: 0.85rem !important;
    }
    
    /* 사이드바 여백 조정 */
    section[data-testid="stSidebar"] > div {
        padding-top: 1rem !important;
    }
    
    /* 채팅 입력창 하단 여백 (푸터 공간 확보) */
    .stChatInputContainer {
        margin-bottom: 3rem !important;
    }
    
    /* 메인 컨텐츠 하단 여백 */
    .main .block-container {
        padding-bottom: 4rem !important;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "config_manager" not in st.session_state:
    st.session_state.config_manager = ConfigManager()

if "vector_store" not in st.session_state:
    config = st.session_state.config_manager.get_all()
    st.session_state.vector_store = VectorStoreManager(
        embedding_api_type=config.get("embedding_api_type", "ollama"),
        embedding_base_url=config["embedding_base_url"],
        embedding_model=config["embedding_model"],
        embedding_api_key=config.get("embedding_api_key", ""),
        distance_function=config.get("chroma_distance_function", "l2")
    )

if "rag_chain" not in st.session_state:
    config = st.session_state.config_manager.get_all()
    multi_query_num = int(config.get("multi_query_num", 3))
    enable_multi_query = config.get("enable_multi_query", True) and multi_query_num > 0
    st.session_state.rag_chain = RAGChain(
        vectorstore=st.session_state.vector_store.get_vectorstore(),
        llm_api_type=config.get("llm_api_type", "ollama"),
        llm_base_url=config["llm_base_url"],
        llm_model=config["llm_model"],
        llm_api_key=config.get("llm_api_key", ""),
        temperature=config.get("temperature", 0.7),
        top_k=config["top_k"],
        # Re-ranker 설정 (기본 활성화)
        use_reranker=config.get("use_reranker", True),
        reranker_model=config.get("reranker_model", "multilingual-mini"),
        reranker_initial_k=config.get("reranker_initial_k", 20),
        # Query Expansion 설정
        enable_synonym_expansion=config.get("enable_synonym_expansion", True),
        enable_multi_query=enable_multi_query,
        multi_query_num=multi_query_num,
        # Diversity Penalty 설정
        diversity_penalty=config.get("diversity_penalty", 0.0),
        diversity_source_key=config.get("diversity_source_key", "source"),
        # Phase 3: File Aggregation (Exhaustive Query → File List)
        enable_file_aggregation=config.get("enable_file_aggregation", False),
        file_aggregation_strategy=config.get("file_aggregation_strategy", "weighted"),
        file_aggregation_top_n=config.get("file_aggregation_top_n", 20),
        file_aggregation_min_chunks=config.get("file_aggregation_min_chunks", 1)
    )

if "chat_history_manager" not in st.session_state:
    st.session_state.chat_history_manager = ChatHistoryManager()

if "doc_processor" not in st.session_state:
    config = st.session_state.config_manager.get_all()
    # RAGChain의 LLM 클라이언트를 DocumentProcessor에 전달 (카테고리 분류용)
    llm_client = st.session_state.rag_chain.llm if "rag_chain" in st.session_state else None
    st.session_state.doc_processor = DocumentProcessor(
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"],
        llm_client=llm_client
    )

# 메인 타이틀
st.title("📚 문서 기반 RAG 시스템")

# 사이드바
with st.sidebar:
    st.header("🎛️ 제어판")
    
    # ==================== 1. 세션 관리 ====================
    with st.expander("💬 세션 관리", expanded=True):
        # 현재 세션 정보 표시
        current_session_info = st.session_state.chat_history_manager.get_all_sessions_with_info()
        current_session = next((s for s in current_session_info if s["session_id"] == st.session_state.session_id), None)
        
        if current_session:
            st.caption(f"📌 {current_session['title']}")
            st.caption(f"💬 대화 수: {len([m for m in st.session_state.messages if m['role'] == 'user'])}")
        else:
            st.caption(f"📌 새 세션")
        
        # 새 세션 시작 버튼
        if st.button("🆕 새 세션 시작", use_container_width=True, type="primary", key="new_session_btn"):
            # 새 세션 ID 생성
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.rag_chain.clear_memory()
            st.success("✅ 새 세션이 시작되었습니다!")
            st.rerun()
        
        st.markdown("**📂 과거 세션**")
        
        all_sessions = st.session_state.chat_history_manager.get_all_sessions_with_info()
        
        if all_sessions:
            # 현재 세션 제외
            past_sessions = [s for s in all_sessions if s["session_id"] != st.session_state.session_id]
            
            if past_sessions:
                for idx, session in enumerate(past_sessions[:10]):  # 최근 10개만 표시
                    col1, col2 = st.columns([5, 1])
                    
                    with col1:
                        # 세션 제목 및 정보 표시
                        st.markdown(f"📝 **{session['title']}**")
                        st.caption(f"💬 {session['message_count']}개 대화 | {session['timestamp'][:10]}")
                    
                    with col2:
                        # 메뉴 버튼 (⋮)
                        with st.popover("⋮", use_container_width=True):
                            st.write("**메뉴**")
                            
                            # 불러오기 버튼
                            if st.button(
                                "📂 불러오기", 
                                key=f"load_{session['session_id']}",
                                use_container_width=True
                            ):
                                # 세션 로드
                                st.session_state.session_id = session['session_id']
                                st.session_state.messages = []
                                st.session_state.rag_chain.clear_memory()
                                st.success(f"✅ '{session['title']}' 세션을 불러왔습니다!")
                                st.rerun()
                            
                            # 삭제 버튼
                            if st.button(
                                "🗑️ 삭제", 
                                key=f"delete_{session['session_id']}",
                                use_container_width=True,
                                type="secondary"
                            ):
                                if st.session_state.chat_history_manager.clear_history(session['session_id']):
                                    st.success("✅ 삭제 완료")
                                    st.rerun()
                    
                    # 마지막 항목이 아닐 때만 구분선 표시
                    if idx < len(past_sessions[:10]) - 1:
                        st.markdown("<hr style='margin: 0.5rem 0; border: 0; border-top: 1px solid #e0e0e0;'>", unsafe_allow_html=True)
            else:
                st.info("현재 세션만 있습니다.")
        else:
            st.info("저장된 세션이 없습니다.")
    
    # ==================== 2. 업로드 ====================
    with st.expander("📤 업로드", expanded=False):
        # 간이 문서 작성
        st.markdown("**✍️ 간이 문서 작성**")
        doc_title = st.text_input(
            "제목",
            placeholder="문서 제목을 입력하세요...",
            key="quick_doc_title"
        )
        doc_content = st.text_area(
            "내용",
            placeholder="문서 내용을 입력하세요...",
            height=150,
            key="quick_doc_content"
        )
        
        if st.button("📝 문서 추가", use_container_width=True, key="add_quick_doc_btn"):
            if doc_title and doc_content:
                try:
                    from langchain.schema import Document
                    from datetime import datetime
                    
                    # Document 객체 생성
                    doc = Document(
                        page_content=doc_content,
                        metadata={
                            "file_name": f"{doc_title}.txt",
                            "file_type": "text",
                            "upload_time": datetime.now().isoformat(),
                            "page_number": 1,
                            "chunk_index": 0,
                            "total_chunks": 1
                        }
                    )
                    
                    # 벡터 저장소에 추가
                    if st.session_state.vector_store.add_documents([doc]):
                        st.success(f"✅ '{doc_title}' 문서가 추가되었습니다!")
                        # 입력 필드 초기화를 위해 rerun
                        st.rerun()
                    else:
                        st.error("❌ 문서 추가에 실패했습니다.")
                except Exception as e:
                    st.error(f"❌ 문서 추가 실패: {str(e)}")
            else:
                st.warning("⚠️ 제목과 내용을 모두 입력해주세요.")
        
        st.markdown("---")
    
    # 파일 업로드
        st.markdown("**📂 파일 업로드**")
    uploaded_files = st.file_uploader(
        "문서를 선택하세요 (PDF, PPT, Excel)",
        type=["pdf", "pptx", "xlsx", "xls"],
            accept_multiple_files=True,
            key="file_uploader"
    )
    
    if uploaded_files:
        if st.button("📥 업로드 및 처리", type="primary", key="upload_btn"):
            with st.spinner("문서를 처리하는 중..."):
                for uploaded_file in uploaded_files:
                    try:
                        # 파일 저장
                        file_path = os.path.join("data/uploaded_files", uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # 파일 타입 확인
                        file_type = st.session_state.doc_processor.get_file_type(uploaded_file.name)
                        
                        # 문서 처리
                        chunks = st.session_state.doc_processor.process_document(
                            file_path, uploaded_file.name, file_type
                        )
                        
                        # 벡터 저장소에 추가
                        st.session_state.vector_store.add_documents(chunks)
                        
                        st.success(f"✅ {uploaded_file.name} 처리 완료 ({len(chunks)} 청크)")
                    except Exception as e:
                        st.error(f"❌ {uploaded_file.name} 처리 실패: {str(e)}")
            
            st.rerun()
    
        st.markdown("**📋 업로드된 파일**")
    documents = st.session_state.vector_store.get_documents_list()
    
    if documents:
        for doc in documents:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{doc['file_name']}**")
                st.caption(f"타입: {doc['file_type']} | 청크: {doc['chunk_count']}")
                st.caption(f"업로드: {doc['upload_time'][:19]}")
            with col2:
                if st.button("🗑️", key=f"delete_{doc['file_name']}"):
                    if st.session_state.vector_store.delete_document(doc['file_name']):
                        st.success(f"✅ {doc['file_name']} 삭제 완료")
                        st.rerun()
                    else:
                        st.error(f"❌ {doc['file_name']} 삭제 실패")
                st.markdown("<hr style='margin: 0.5rem 0; border: 0; border-top: 1px solid #e0e0e0;'>", unsafe_allow_html=True)
    else:
        st.info("업로드된 파일이 없습니다.")
    
    # ==================== 3. 설정 ====================
    with st.expander("⚙️ 설정", expanded=False):
        # 현재 설정 로드
        config = st.session_state.config_manager.get_all()
        
        st.markdown("**🤖 LLM 설정**")
        llm_api_type = st.selectbox(
            "LLM API 타입",
            options=["request", "ollama", "openai", "openai-compatible"],
            index=["request", "ollama", "openai", "openai-compatible"].index(config.get("llm_api_type", "request")),
            help="Request: HTTP 요청 (메모리 효율적) / Ollama: LangChain 래퍼 / OpenAI: 공식 API / OpenAI Compatible: 호환 API",
            key="llm_api_type_select"
        )
        llm_base_url = st.text_input(
            "LLM 서버 주소", 
            value=config["llm_base_url"],
            help="Ollama: http://localhost:11434 / OpenAI Compatible: 사내 API 주소",
            key="llm_base_url_input"
        )
        llm_model = st.text_input(
            "LLM 모델명", 
            value=config["llm_model"],
            help="예: llama3, gpt-4, gpt-3.5-turbo",
            key="llm_model_input"
        )
        llm_api_key = st.text_input(
            "LLM API 키 (선택사항)", 
            value=config.get("llm_api_key", ""),
            type="password",
            help="OpenAI API 키 (Ollama는 불필요)",
            key="llm_api_key_input"
        )
        temperature = st.slider(
            "Temperature (온도)",
            min_value=0.0,
            max_value=2.0,
            value=config.get("temperature", 0.7),
            step=0.1,
            help="낮음(0.1-0.3): 일관적/정확 | 중간(0.5-0.7): 균형 | 높음(0.8-1.0): 창의적/다양",
            key="temperature_input"
        )
        
        st.markdown("**🔍 임베딩 설정**")
        embedding_api_type = st.selectbox(
            "임베딩 API 타입",
            options=["request", "ollama", "openai", "openai-compatible"],
            index=["request", "ollama", "openai", "openai-compatible"].index(config.get("embedding_api_type", "ollama")),
            help="Request: HTTP 요청 (메모리 효율적) / Ollama: LangChain 래퍼 / OpenAI: 공식 OpenAI API / OpenAI Compatible: 호환 API",
            key="embedding_api_type_select"
        )
        embedding_base_url = st.text_input(
            "임베딩 서버 주소", 
            value=config["embedding_base_url"],
            help="Ollama: http://localhost:11434 / OpenAI Compatible: 사내 API 주소",
            key="embedding_base_url_input"
        )
        embedding_model = st.text_input(
            "임베딩 모델명", 
            value=config["embedding_model"],
            help="예: nomic-embed-text, text-embedding-ada-002",
            key="embedding_model_input"
        )
        embedding_api_key = st.text_input(
            "임베딩 API 키 (선택사항)", 
            value=config.get("embedding_api_key", ""),
            type="password",
            help="OpenAI API 키 (Ollama는 불필요)",
            key="embedding_api_key_input"
        )
        
        st.markdown("**📄 문서 처리 설정**")
        chunk_size = st.number_input("청크 크기", min_value=100, max_value=2000, value=config["chunk_size"], key="chunk_size_input")
        if chunk_size != 1500:
            st.warning(f"⚠️ 권장값은 1500입니다. 변경 시 DB를 재구축해야 합니다!")
        chunk_overlap = st.number_input("청크 오버랩", min_value=0, max_value=500, value=config["chunk_overlap"], key="chunk_overlap_input")
        if chunk_overlap != 200:
            st.warning(f"⚠️ 권장값은 200입니다.")
        top_k = st.number_input("검색 결과 수 (Top K)", min_value=1, max_value=10, value=config["top_k"], key="top_k_input")
        
        # 설정 저장 버튼
        if st.button("💾 설정 저장", type="primary", use_container_width=True, key="save_config_btn"):
            new_config = {
                "llm_api_type": llm_api_type,
                "llm_base_url": llm_base_url,
                "llm_model": llm_model,
                "llm_api_key": llm_api_key,
                "temperature": temperature,
                "embedding_api_type": embedding_api_type,
                "embedding_base_url": embedding_base_url,
                "embedding_model": embedding_model,
                "embedding_api_key": embedding_api_key,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "top_k": top_k
            }
            
            if st.session_state.config_manager.save_config(new_config):
                # 설정 변경 시 컴포넌트 업데이트
                st.session_state.vector_store.update_embeddings(
                    embedding_api_type, embedding_base_url, embedding_model, embedding_api_key
                )
                st.session_state.rag_chain.update_llm(
                    llm_api_type, llm_base_url, llm_model, llm_api_key, temperature
                )
                st.session_state.rag_chain.update_retriever(
                    st.session_state.vector_store.get_vectorstore(),
                    top_k
                )
                # LLM 클라이언트를 DocumentProcessor에 전달 (카테고리 분류용)
                st.session_state.doc_processor = DocumentProcessor(
                    chunk_size,
                    chunk_overlap,
                    llm_client=st.session_state.rag_chain.llm
                )
                st.success("✅ 설정이 저장되었습니다!")
                st.rerun()
            else:
                st.error("❌ 설정 저장에 실패했습니다.")

# 메인 영역 - 채팅 인터페이스
st.header("💬 대화")

# 세션 이력 로드 (최초 1회)
if not st.session_state.messages:
    history = st.session_state.chat_history_manager.load_history(st.session_state.session_id)
    for msg in history:
        st.session_state.messages.append({
            "role": "user",
            "content": msg["question"]
        })
        st.session_state.messages.append({
            "role": "assistant",
            "content": msg["answer"],
            "sources": msg.get("sources", [])
        })

# 채팅 메시지 표시
for message in st.session_state.messages:
    if message["role"] == "user":
        # 사용자 메시지 - 오른쪽 정렬
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-end; align-items: flex-start; margin-bottom: 1rem; gap: 0.5rem;">
            <div style="max-width: 70%; background-color: #e3f2fd; border-radius: 15px; padding: 0.75rem 1rem; text-align: left;">
                {message["content"]}
            </div>
            <div style="width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; flex-shrink: 0; color: white; font-weight: bold; font-size: 1rem;">
                👤
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # AI 메시지 - 왼쪽 정렬, 전체 너비
        with st.chat_message("assistant"):
            st.write(message["content"])
            
            # 출처 정보 표시
            if "sources" in message and message["sources"]:
                with st.expander("📎 출처 정보 (유사도 점수 포함)"):
                    for idx, source in enumerate(message["sources"], 1):
                        st.write(f"**{idx}. {source['file_name']}** (페이지: {source['page_number']})")
                        
                        # 유사도 점수가 있는 경우 표시
                        if 'similarity_score' in source:
                            # 점수는 이미 0-100 범위로 정규화되어 있음 (rag_chain.py에서 처리)
                            similarity_percent = source['similarity_score']
                            st.write(f"🎯 유사도: {similarity_percent:.1f}%")
                        
                        st.caption(source['content'])
                        st.divider()

# 사용자 입력
if prompt := st.chat_input("질문을 입력하세요..."):
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 사용자 메시지 표시 - 오른쪽 정렬
    st.markdown(f"""
    <div style="display: flex; justify-content: flex-end; align-items: flex-start; margin-bottom: 1rem; gap: 0.5rem;">
        <div style="max-width: 70%; background-color: #e3f2fd; border-radius: 15px; padding: 0.75rem 1rem; text-align: left;">
            {prompt}
        </div>
        <div style="width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; flex-shrink: 0; color: white; font-weight: bold; font-size: 1rem;">
            👤
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # RAG 체인으로 스트리밍 답변 생성
    with st.chat_message("assistant"):
        # 스트리밍 답변 생성
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # 현재 메시지를 제외한 이전 대화 이력 전달
            chat_history = st.session_state.messages[:-1]  # 방금 추가한 사용자 메시지 제외
            
            # 스트리밍으로 답변 표시 (대화 이력 포함)
            for chunk in st.session_state.rag_chain.query_stream(prompt, chat_history):
                full_response += chunk
                message_placeholder.markdown(full_response + "▌")
            
            # 최종 답변 표시
            message_placeholder.markdown(full_response)
            
            # 출처 정보 가져오기 (유사도 점수 포함)
            sources = st.session_state.rag_chain.get_source_documents(prompt)
            
            # 출처 정보 표시
            if sources:
                with st.expander("📎 출처 정보 (유사도 점수 포함)"):
                    for idx, source in enumerate(sources, 1):
                        # 유사도 점수를 백분율로 변환
                        score = source['similarity_score']
                        # Re-ranker 점수 (0~10, 높을수록 좋음) vs Vector Search distance (0~2, 낮을수록 좋음)
                        if score > 3:  # Re-ranker 점수
                            similarity_percent = (score / 10) * 100
                        else:  # Vector Search distance
                            similarity_percent = max(0, 100 - (score * 20))
                        
                        st.write(f"**{idx}. {source['file_name']}** (페이지: {source['page_number']})")
                        st.write(f"🎯 유사도: {similarity_percent:.1f}% (Re-rank 점수: {score:.4f})")
                        st.caption(source['content'])
                        st.divider()
            
            # 메시지 저장
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_response,
                "sources": sources
            })
            
            # 대화 이력 파일에 저장
            st.session_state.chat_history_manager.save_message(
                st.session_state.session_id,
                prompt,
                full_response,
                sources
            )
            
        except Exception as e:
            error_msg = f"오류가 발생했습니다: {str(e)}"
            st.error(error_msg)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg
            })

# 푸터 (화면 하단 고정)
st.markdown("""
<div style="
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    background-color: var(--background-color);
    padding: 0.5rem 1rem;
    text-align: center;
    font-size: 0.75rem;
    color: var(--text-color);
    border-top: 1px solid #e0e0e0;
    z-index: 999;
">
    🚀 전문 문서 기반 RAG 시스템 | LangChain + ChromaDB + Streamlit
</div>
""", unsafe_allow_html=True)

