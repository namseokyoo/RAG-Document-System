2.4. Text (TXT, MD, Code) 고급 청킹 전략 (의사 코드)
이 문서는 TXT 파일의 내용을 분석하여 **암묵적 구조(implicit structure)**를 감지하고, "섹션(Section)" 또는 "파일 전체(File)"를 '부모 청크'로, "문단(Paragraph)", "코드 블록(Code Block)", "리스트(List)" 등을 '자식 청크'로 분리하는 전략을 정의합니다.

2.4.1. Text 파일의 핵심 전략: 유형 라우팅 (Type Routing)
"Text" 파일은 .txt뿐만 아니라 .md, .py, .js, .json, .csv 등 다양한 형식을 포함할 수 있습니다. 가장 효과적인 청킹을 위해, 파일의 확장자나 내용을 분석하여 유형을 먼저 파악하고, 각 유형에 최적화된 청킹 로직으로 라우팅해야 합니다.

Python

FUNCTION process_text_document(file_path, config):
    """
    (메인 라우터) 파일 유형을 감지하여 최적의 청킹 함수를 호출합니다.
    """
    content = read_file_content(file_path)
    file_type = detect_text_file_type(file_path, content) # (핵심 헬퍼 1)
    
    document_id = generate_uuid()
    all_chunks = []
    
    IF file_type == "MARKDOWN_OR_PROSE":
        # 일반 글, 마크다운 (가장 일반적인 케이스)
        all_chunks = process_prose_document(content, document_id, config)
        
    ELIF file_type == "SOURCE_CODE":
        # .py, .js, .java 등
        language = get_language_from_extension(file_path)
        all_chunks = process_code_document(content, language, document_id, config)
        
    ELIF file_type == "CSV":
        # .csv, .tsv (XLSX 전략과 유사하게 처리)
        all_chunks = process_csv_document(content, document_id, config)
        
    ELIF file_type == "JSON":
        # .json (키-값 쌍 기반으로 청킹)
        all_chunks = process_json_document(content, document_id, config)
    
    ELSE: # (예: 단순 .txt)
        # 기본 산문 처리 로직 적용
        all_chunks = process_prose_document(content, document_id, config)
        
    RETURN all_chunks
2.4.2. (주요 전략) 산문/마크다운 (Prose/Markdown) 청킹
이 전략은 Markdown의 헤더(##)나 구분선(---)을 기준으로 **'섹션(Section)'**을 나누고, 각 섹션을 '부모 청크(Large Chunk)'로, 그 안의 요소(문단, 코드 블록 등)를 '자식 청크(Small Chunks)'로 만듭니다.

2.4.2.1. 데이터 구조 (Metadata)
Python

class Metadata:
    document_id: string
    file_type: string       # "PROSE", "CODE" 등
    
    # 계층 구조 (Small-to-Large)
    parent_chunk_id: string # 이 청크가 속한 '섹션' 청크의 ID
    section_title: string   # (핵심) 이 청크가 속한 가장 가까운 상위 헤더
    
    # 검색 가중치
    chunk_type: string      # header, paragraph, code_block, list, section_summary
    chunk_type_weight: float # (예: header=2.0)
2.4.2.2. 메인 프로세스 (Prose/Markdown)
Python

FUNCTION process_prose_document(content, document_id, config):
    """
    Markdown/일반 텍스트를 '섹션' 기반으로 계층적 청킹을 수행합니다.
    """
    all_chunks = []
    
    # 1. (핵심 헬퍼 2) 내용을 의미론적 요소(헤더, 문단, 코드블록 등)로 파싱
    elements = parse_text_elements(content) # [Element(type="header", content="# H1"), Element(type="paragraph", ...)]
    
    current_section_title = "문서 서두" # 현재 섹션 제목 추적
    current_section_content_buffer = [] # '부모 청크'용 텍스트 버퍼
    current_section_id = generate_uuid() # 현재 '부모 청크' ID

    FOR elem IN elements:
        
        # --- [전략 1: 헤더(Header) 감지 시] ---
        # 헤더는 새 섹션의 시작을 의미
        IF elem.type == "header":
            
            # 1a. 이전 섹션의 '부모 청크(Large Chunk)'를 먼저 생성
            IF is_not_empty(current_section_content_buffer):
                section_content = "\n\n".join(current_section_content_buffer)
                section_chunk = create_chunk(
                    id=current_section_id,
                    content=section_content,
                    chunk_type="section_summary",
                    metadata={
                        "document_id": document_id,
                        "section_title": current_section_title,
                        "parent_chunk_id": None,
                        "chunk_type_weight": 0.5
                    }
                )
                all_chunks.append(section_chunk)
            
            # 1b. 새 섹션 정보로 업데이트
            current_section_title = elem.content
            current_section_content_buffer = [] # 부모 청크 버퍼 리셋
            current_section_id = generate_uuid() # 새 부모 ID 생성
            
            # 1c. 헤더 자체도 '자식 청크(Small Chunk)'로 생성 (검색 가중치 높게)
            header_chunk = create_chunk(
                id=generate_uuid(),
                content=elem.content,
                chunk_type="header",
                metadata={
                    "document_id": document_id,
                    "parent_chunk_id": current_section_id, # 새 부모 ID를 가리킴
                    "section_title": current_section_title,
                    "chunk_type_weight": 2.0
                }
            )
            all_chunks.append(header_chunk)
        
        # --- [전략 2: 일반 요소 (문단, 코드, 리스트) 감지 시] ---
        ELSE:
            # 2a. 현재 섹션의 '부모 청크' 버퍼에 내용 추가
            current_section_content_buffer.append(elem.content)
            
            # 2b. 요소를 '자식 청크(Small Chunk)'로 생성 (Fallback 적용)
            # (요소 자체가 max_size보다 클 수 있으므로)
            small_chunks = chunk_element_with_fallback(
                content=elem.content,
                type=elem.type, # "paragraph", "code_block", "list"
                config=config,
                base_metadata={
                    "document_id": document_id,
                    "parent_chunk_id": current_section_id,
                    "section_title": current_section_title,
                    "chunk_type_weight": 1.0 # (유형별로 가중치 조절 가능)
                }
            )
            all_chunks.extend(small_chunks)

    # 3. 루프 종료 후, 마지막 섹션의 '부모 청크' 처리
    IF is_not_empty(current_section_content_buffer):
        section_content = "\n\n".join(current_section_content_buffer)
        section_chunk = create_chunk(
            id=current_section_id,
            content=section_content,
            chunk_type="section_summary",
            metadata={
                "document_id": document_id,
                "section_title": current_section_title,
                "parent_chunk_id": None,
                "chunk_type_weight": 0.5
            }
        )
        all_chunks.append(section_chunk)
        
    RETURN all_chunks
2.4.3. (특수 전략) 소스 코드 (Source Code) 청킹
Python

FUNCTION process_code_document(content, language, document_id, config):
    """
    (LangChain/LlamaIndex의 LanguageRecursiveCharacterTextSplitter와 유사)
    소스 코드를 클래스, 함수 등 언어 구조에 맞춰 분할합니다.
    """
    all_chunks = []
    
    # 1. 언어별 구분자 가져오기
    # 예: language == "python" -> [ "\nclass ", "\ndef ", "\n\tdef " ]
    separators = Language.get_separators(language) 
    
    # 2. 재귀적으로 분할 (가장 큰 단위인 '클래스'부터 시도)
    code_splits = recursive_text_split(content, separators, config.max_size)
    
    FOR split IN code_splits:
        # 3. 청크의 첫 줄을 분석하여 유형(클래스, 함수) 파악
        chunk_type = "code_segment"
        if split.strip().starts_with("class "):
            chunk_type = "code_class"
        elif split.strip().starts_with("def "):
            chunk_type = "code_function"
            
        chunk = create_chunk(
            id=generate_uuid(),
            content=split,
            chunk_type=chunk_type,
            metadata={
                "document_id": document_id,
                "language": language,
                "parent_chunk_id": None, # (단순화를 위해 계층 구조 생략 가능)
                "chunk_type_weight": 1.2
            }
        )
        all_chunks.append(chunk)
        
    RETURN all_chunks
2.4.4. 핵심 헬퍼 함수 (Helper Functions)
Python

FUNCTION detect_text_file_type(file_path, content_snippet):
    """ (핵심 헬퍼 1) 파일 확장자와 내용을 기반으로 파일 유형을 추론합니다. """
    extension = get_file_extension(file_path).lower()
    
    IF extension IN [".md", ".markdown"]:
        RETURN "MARKDOWN_OR_PROSE"
    IF extension IN [".py", ".js", ".java", ".c", ".cpp", ".go", ".rs"]:
        RETURN "SOURCE_CODE"
    IF extension == ".csv":
        RETURN "CSV"
    IF extension == ".json":
        RETURN "JSON"
    
    # 확장자가 .txt이거나 없는 경우, 내용 기반 추론
    IF content_snippet.strip().starts_with("{") OR content_snippet.strip().starts_with("["):
        RETURN "JSON"
    IF content_snippet.contains("```") OR content_snippet.contains("##"):
        RETURN "MARKDOWN_OR_PROSE"
    IF content_snippet.contains("def ") AND content_snippet.contains("class "):
        RETURN "SOURCE_CODE" # Python으로 추정
    
    RETURN "PROSE" # 기본값

FUNCTION parse_text_elements(content):
    """
    (핵심 헬퍼 2) 정규식을 사용하여 텍스트를 구조적 요소 리스트로 변환합니다.
    (구현: unstructured.io 라이브러리의 partition_text()와 유사한 로직)
    """
    elements = []
    
    # (전략: 복잡한 정규식으로 코드블록, 테이블 등을 먼저 찾고, 나머지를 \n\n로 분할)
    
    # 1. (예시) 코드 블록(```...```)을 먼저 찾아서 분리
    code_pattern = r"(```[\s\S]*?```)"
    parts = re.split(code_pattern, content)
    
    FOR part IN parts:
        IF re.match(code_pattern, part):
            elements.append(Element(type="code_block", content=part))
        ELSE:
            # 2. 코드 블록이 아닌 부분을 문단(헤더, 리스트, 일반 문단)으로 재분할
            # ( \n\n 기준으로 분할 후, 각 문단을 다시 classify_text_paragraph_type)
            paragraphs = part.split("\n\n")
            FOR para IN paragraphs:
                IF is_empty(para):
                    CONTINUE
                
                # (사용자 원본 문서의 분류 로직 활용)
                para_type = classify_text_paragraph_type(para) # "header", "list", "paragraph"
                elements.append(Element(type=para_type, content=para))
                
    RETURN elements

FUNCTION classify_text_paragraph_type(paragraph):
    """ (사용자 원본 문서의 헬퍼) 문단 유형 분류 """
    if re.search(r'^#+\s', paragraph):  # Markdown 헤더
        return "header"
    elif re.search(r'^\d+\.|^[-*]', paragraph, re.MULTILINE):  # 리스트
        return "list"
    elif re.search(r'\|.*\|', paragraph, re.MULTILINE):  # 표
        return "table"
    else:
        return "paragraph"

# --- (PDF/PPTX/XLSX 전략과 공유되는 헬퍼 함수) ---
FUNCTION chunk_element_with_fallback(content, type, config, base_metadata):
    """
    (공유 헬퍼) 요소가 max_size를 초과할 경우 재귀적으로 분할합니다.
    """
    # ... (PDF 의사 코드와 동일한 로직) ...