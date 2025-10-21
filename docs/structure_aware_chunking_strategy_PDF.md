2.1. PDF 고급 청킹 전략 (의사 코드)
이 전략은 PDF의 시각적/구조적 레이아웃을 분석하여, 의미론적으로 완전한 '자식 청크(Small Chunks)'를 생성하고, 이들을 '부모 청크(Large Chunks)'와 연결하는 "Small-to-Large" 검색 아키텍처를 구현하는 것을 목표로 합니다.

2.1.1. 핵심 데이터 구조 (Data Structures)
Python

# 청크의 최종 형태
class Chunk:
    id: string              # 고유 UUID (예: chunk_abc_123)
    content: string         # 청크의 텍스트 내용
    chunk_type: string      # 요소 유형 (title, paragraph, table, list, page_summary)
    metadata: Metadata      # 아래에 정의된 메타데이터 객체

# RAG 검색 및 필터링의 핵심이 되는 메타데이터
class Metadata:
    document_id: string     # 원본 문서 ID
    page_number: int        # 원본 페이지 번호
    
    # 계층 구조 (Hierarchy)
    parent_chunk_id: string # "Small-to-Large"를 위한 부모 청크 ID (예: 페이지 전체 ID)
    section_title: string   # 이 청크가 속한 가장 가까운 상위 제목
    
    # 레이아웃 정보 (Layout-Aware)
    chunk_type_weight: float # 청크 유형별 가중치 (예: title=2.0)
    font_size: float        # 텍스트의 평균 폰트 크기
    is_bold: bool           # 텍스트의 굵기 여부
    coordinates: tuple      # 페이지 내 (x1, y1, x2, y2) 좌표 (선택적)
2.1.2. 메인 프로세스 (Main Process)
Python

FUNCTION process_pdf_document(pdf_path, config):
    """
    PDF 문서를 레이아웃을 인식하여 계층적으로 청킹합니다.
    (구현 시: pdfplumber, unstructured.io, PyMuPDF 등 라이브러리 활용)
    """
    
    all_chunks = []
    document_id = generate_uuid()
    pdf = open_pdf_with_layout_parser(pdf_path) # Layout-Aware 파서로 PDF 열기
    
    current_section_title = "문서 서두" # 현재 섹션 제목 추적
    
    FOR page IN pdf.pages:
        page_number = page.page_number
        
        # --- [전략 1: "Large" 청크 생성] ---
        # "Small-to-Large" 검색을 위해 페이지 전체 텍스트를 부모 청크로 우선 생성.
        # (대안: 페이지 요약 모델을 돌려 요약본을 'Large' 청크로 사용)
        page_id = f"{document_id}_page_{page_number}"
        page_full_text = page.extract_text()
        
        page_summary_chunk = create_chunk(
            id=page_id,
            content=page_full_text,
            chunk_type="page_summary",
            metadata={
                "document_id": document_id,
                "page_number": page_number,
                "parent_chunk_id": None, # 최상위 부모
                "section_title": current_section_title
            }
        )
        all_chunks.append(page_summary_chunk)
        
        # --- [전략 2: "Small" 청크 생성 (Layout-Aware)] ---
        # 페이지의 시각적/구조적 요소를 분석
        elements = analyze_page_elements(page) # 헬퍼 함수 (가장 중요)
        
        current_list_buffer = [] # 리스트 항목을 모으기 위한 버퍼
        
        FOR elem IN elements:
            
            # 2a. 리스트 항목 처리 (버퍼링)
            # 리스트 항목(예: • 항목1, • 항목2)은 개별로 청킹하면 문맥이 깨짐.
            # 연속된 리스트 항목을 버퍼에 모아서 하나의 청크로 만듦.
            IF elem.type == "list_item":
                current_list_buffer.append(elem.content)
                CONTINUE # 다음 요소로
            
            # 2b. 버퍼 비우기 (리스트가 끝났을 때)
            IF is_not_empty(current_list_buffer):
                list_content = "\n".join(current_list_buffer)
                # 리스트 청크도 너무 길 수 있으므로, Fallback 청킹 함수 사용
                list_chunks = chunk_element_with_fallback(
                    content=list_content,
                    type="list",
                    config=config,
                    base_metadata={
                        "document_id": document_id,
                        "page_number": page_number,
                        "parent_chunk_id": page_id, # 부모 = 페이지 청크
                        "section_title": current_section_title,
                        "font_size": elem.properties.font_size
                    }
                )
                all_chunks.extend(list_chunks)
                current_list_buffer.clear()
            
            
            # 2c. 제목(Title) 처리
            IF elem.type == "title":
                current_section_title = elem.content # 현재 섹션 제목 업데이트
                
                # 제목은 그 자체로 중요한 청크가 됨 (Fallback 거의 불필요)
                chunk = create_chunk(
                    id=generate_uuid(),
                    content=elem.content,
                    chunk_type="title",
                    metadata={
                        "document_id": document_id,
                        "page_number": page_number,
                        "parent_chunk_id": page_id,
                        "section_title": current_section_title,
                        "font_size": elem.properties.font_size,
                        "is_bold": elem.properties.is_bold,
                        "chunk_type_weight": 2.0 # 검색 가중치
                    }
                )
                all_chunks.append(chunk)

            # 2d. 문단(Paragraph) 처리
            ELIF elem.type == "paragraph":
                # 문단이 config.max_size보다 클 수 있으므로, Fallback 청킹
                para_chunks = chunk_element_with_fallback(
                    content=elem.content,
                    type="paragraph",
                    config=config,
                    base_metadata={
                        "document_id": document_id,
                        "page_number": page_number,
                        "parent_chunk_id": page_id,
                        "section_title": current_section_title,
                        "font_size": elem.properties.font_size
                    }
                )
                all_chunks.extend(para_chunks)

            # 2e. 테이블(Table) 처리
            ELIF elem.type == "table":
                # 테이블은 별도 전략 헬퍼 함수로 처리
                table_chunks = chunk_table_strategically(
                    table_data=elem.data, # 테이블 데이터 (e.g., list of lists)
                    config=config,
                    base_metadata={
                        "document_id": document_id,
                        "page_number": page_number,
                        "parent_chunk_id": page_id,
                        "section_title": current_section_title
                    }
                )
                all_chunks.extend(table_chunks)
                
            # 2f. 기타 요소 (e.g., 이미지 캡션, 머리글/바닥글)
            # (전략에 따라 포함하거나 무시)

        # 페이지의 마지막에 도달했을 때, 리스트 버퍼가 남아있다면 처리
        IF is_not_empty(current_list_buffer):
            list_content = "\n".join(current_list_buffer)
            list_chunks = chunk_element_with_fallback(
                content=list_content,
                type="list",
                config=config,
                base_metadata={...} # 위와 동일
            )
            all_chunks.extend(list_chunks)
            current_list_buffer.clear()
            
    RETURN all_chunks
2.1.3. 핵심 헬퍼 함수 (Helper Functions)
Python

FUNCTION analyze_page_elements(page_object):
    """
    (가장 중요) PDF 페이지 객체를 받아, 시각적 요소를 분석하고 구조화된 리스트 반환.
    (구현: pdfplumber.objects, unstructured.partition_pdf, PyMuPDF.get_text("blocks"))
    """
    
    # 1. 페이지 내의 모든 텍스트 블록과 폰트 정보(크기, 굵기) 추출
    # 2. (선택적) 페이지 내의 모든 선(line)과 사각형(rect)을 추출하여 테이블 경계 식별
    
    structured_elements_list = []
    
    # 3. 폰트 크기 통계(예: 평균, 표준편차)를 계산하여 제목 레벨(h1, h2, h3) 임계값 결정
    title_font_threshold = 18.0
    
    FOR block IN page_text_blocks:
        # 4. 블록의 폰트 크기/굵기를 기준으로 요소 유형 분류
        IF block.font_size > title_font_threshold AND block.is_bold:
            structured_elements_list.append(Element(type="title", content=block.text, properties={...}))
        
        # 5. 블록의 시작이 '•', '-', '1.' 등인지 확인하여 리스트 분류
        ELIF block.text.starts_with("•") OR block.text.starts_with_number():
            structured_elements_list.append(Element(type="list_item", content=block.text, properties={...}))
        
        # 6. 나머지는 일반 문단으로 분류
        ELSE:
            structured_elements_list.append(Element(type="paragraph", content=block.text, properties={...}))
    
    # 7. page.extract_tables() (pdfplumber) 또는 유사 함수로 테이블 추출
    FOR table IN page_tables:
        structured_elements_list.append(Element(type="table", data=table.data, properties={...}))
    
    # 8. 모든 요소를 페이지 내 시각적 순서(y좌표, x좌표)대로 정렬하여 반환
    RETURN sort_elements_by_position(structured_elements_list)


FUNCTION chunk_element_with_fallback(content, type, config, base_metadata):
    """
    의미론적 요소(문단, 리스트)가 max_size를 초과할 경우,
    RecursiveCharacterTextSplitter (Fallback)를 적용하여 강제 분할.
    """
    chunks = []
    
    IF len(content) <= config.max_size:
        # 단일 청크로 충분
        chunk = create_chunk(
            id=generate_uuid(),
            content=content,
            chunk_type=type,
            metadata=base_metadata
        )
        chunks.append(chunk)
    ELSE:
        # Fallback: max_size를 초과하면, 문장/단어 기준으로 강제 분할
        sub_chunks_content = recursive_text_split(
            content,
            chunk_size=config.max_size,
            chunk_overlap=config.overlap_size
        )
        
        FOR sub_content IN sub_chunks_content:
            # 원본 타입을 유지하되, 분할되었음을 명시 (예: "paragraph_segment")
            chunk = create_chunk(
                id=generate_uuid(),
                content=sub_content,
                chunk_type=f"{type}_segment",
                metadata=base_metadata
            )
            chunks.append(chunk)
            
    RETURN chunks


FUNCTION chunk_table_strategically(table_data, config, base_metadata):
    """
    테이블 데이터를 RAG에 적합하게 청킹합니다.
    (전략: Markdown 변환 후 Fallback 적용)
    """
    
    # 전략: 테이블을 Markdown 형식의 텍스트로 변환 (가장 일반적)
    markdown_table = convert_table_to_markdown(table_data)
    
    # 테이블 텍스트가 너무 클 수 있으므로, Fallback 청킹 적용
    table_chunks = chunk_element_with_fallback(
        content=markdown_table,
        type="table",
        config=config,
        base_metadata=base_metadata
    )
    
    # (대안 전략: 테이블을 요약하는 LLM 호출 후, 요약본을 청킹)
    # (대안 전략: 헤더 + N개 행 단위로 청킹. XLSX 전략과 유사)
    
    RETURN table_chunks