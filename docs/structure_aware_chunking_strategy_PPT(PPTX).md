2.2. PPT/PPTX 고급 청킹 전략 (의사 코드)
이 문서는 python-pptx 라이브러리를 사용하여 PPTX 파일의 고유한 구조(슬라이드, 도형, 노트)를 정밀하게 분석하고, RAG 검색에 최적화된 **계층적 청크(Hierarchical Chunks)**를 생성하는 전략을 정의합니다.

2.2.1. python-pptx 라이브러리 핵심 개념
RAG 청킹을 위해 python-pptx의 다음 객체들을 활용해야 합니다.

Presentation(path): PPTX 파일 전체를 나타내는 루트 객체입니다.

presentation.slides: 프레젠테이션 내의 모든 Slide 객체에 대한 리스트입니다.

Slide: 개별 슬라이드. 청킹의 기본이 되는 '문맥(Large Chunk)' 단위입니다.

slide.shapes: 슬라이드 내의 모든 Shape 객체(텍스트 상자, 이미지, 표 등) 리스트입니다.

slide.shapes.title: 슬라이드의 '제목' Shape 객체입니다.

slide.notes_slide: 슬라이드의 '발표자 노트'를 담고 있는 NotesSlide 객체입니다. RAG에서 매우 중요한 텍스트 소스입니다.

shape.has_text_frame: 해당 Shape가 텍스트를 포함하는지 (e.g., True).

shape.text_frame: 텍스트를 담고 있는 TextFrame 객체입니다.

text_frame.paragraphs: TextFrame 내의 모든 Paragraph 객체 리스트 (일반적으로 불릿 포인트 하나가 Paragraph 하나입니다).

paragraph.level: (핵심) 해당 문단의 들여쓰기 수준 (0이 최상위 불릿, 1이 하위 불릿). 불릿 그룹핑에 결정적입니다.

shape.has_table: 해당 Shape가 표인지 (e.g., True).

shape.table: 표 데이터를 담고 있는 Table 객체입니다.

2.2.2. 핵심 데이터 구조 (Data Structures)
Chunk 클래스 (PDF 전략과 동일)

Metadata 클래스 (PPTX 특화):

Python

class Metadata:
    document_id: string     # 원본 문서 ID
    slide_number: int       # RAG 필터링의 핵심 (예: "3번 슬라이드 요약해줘")
    
    # 계층 구조 (Small-to-Large)
    parent_chunk_id: string # 이 청크가 속한 '슬라이드 요약' 청크의 ID
    
    # 검색 가중치
    chunk_type: string      # slide_title, bullet_group, slide_notes, table, slide_summary
    chunk_type_weight: float # 청크 유형별 가중치 (예: title=2.0, notes=1.5, bullet=1.0)
2.2.3. 메인 프로세스 (Main Process)
Python

# python-pptx 라이브러리 임포트
from pptx import Presentation

FUNCTION process_pptx_document(pptx_path, config):
    """
    python-pptx를 사용하여 PPTX 문서를 슬라이드 구조 인식 기반으로 청킹합니다.
    """
    
    all_chunks = []
    document_id = generate_uuid()
    presentation = Presentation(pptx_path) # 1. PPTX 파일 열기
    
    # 2. 모든 슬라이드를 순회
    FOR slide_index, slide IN enumerate(presentation.slides):
        slide_number = slide_index + 1
        slide_id = f"{document_id}_slide_{slide_number}" # 슬라이드 고유 ID (부모 ID가 됨)
        
        # --- [전략 1: "Large" 청크 생성 (부모 문맥)] ---
        # 슬라이드 전체 텍스트를 '부모 청크'로 생성 (Small-to-Large 검색용)
        # 이 청크는 검색 결과의 문맥을 보강하는 데 사용됩니다.
        slide_full_text = extract_full_text_from_slide_shapes(slide)
        
        slide_summary_chunk = create_chunk(
            id=slide_id,
            content=slide_full_text,
            chunk_type="slide_summary", # 부모 청크
            metadata={
                "document_id": document_id,
                "slide_number": slide_number,
                "parent_chunk_id": None, # 최상위
                "chunk_type_weight": 0.5 # 직접 검색될 확률은 낮춤
            }
        )
        all_chunks.append(slide_summary_chunk)
        
        
        # --- [전략 2: "Small" 청크 생성 (자식 검색 대상)] ---
        
        # 2a. 슬라이드 제목 (Slide Title)
        # 제목은 가장 중요한 정보. (python-pptx의 .title 속성 활용)
        IF slide.shapes.title IS NOT None AND slide.shapes.title.has_text_frame:
            title_text = slide.shapes.title.text_frame.text
            IF is_not_empty(title_text):
                chunk = create_chunk(
                    id=generate_uuid(),
                    content=title_text,
                    chunk_type="slide_title",
                    metadata={
                        "document_id": document_id,
                        "slide_number": slide_number,
                        "parent_chunk_id": slide_id, # 부모 = 슬라이드 요약 청크
                        "chunk_type_weight": 2.0 # 검색 가중치 높게
                    }
                )
                all_chunks.append(chunk)

        # 2b. 슬라이드 노트 (Slide Notes)
        # 발표자 노트는 핵심 요약/스크립트이므로 매우 중요. (.notes_slide 활용)
        IF slide.notes_slide IS NOT None AND slide.notes_slide.notes_text_frame IS NOT None:
            notes_text = slide.notes_slide.notes_text_frame.text
            IF is_not_empty(notes_text):
                # 노트가 길 수 있으므로, Fallback 청킹 적용
                notes_chunks = chunk_element_with_fallback(
                    content=notes_text,
                    type="slide_notes",
                    config=config,
                    base_metadata={
                        "document_id": document_id,
                        "slide_number": slide_number,
                        "parent_chunk_id": slide_id,
                        "chunk_type_weight": 1.7 # 가중치 높게
                    }
                )
                all_chunks.extend(notes_chunks)
        
        
        # 2c. 슬라이드 본문 (도형 순회)
        # 제목과 노트를 제외한 모든 텍스트/표 도형(.shapes) 순회
        FOR shape IN slide.shapes:
            # 이미 처리한 제목은 건너뜀
            IF shape.is_placeholder AND shape.placeholder_format.type == "TITLE":
                CONTINUE
                
            # (1) 본문 텍스트 (불릿 포인트)
            IF shape.has_text_frame:
                # 텍스트 프레임(본문)의 불릿 포인트를 '들여쓰기' 기준으로 그룹화
                bullet_chunks = chunk_bullet_points_by_level(
                    text_frame=shape.text_frame, # TextFrame 객체 전달
                    config=config,
                    base_metadata={
                        "document_id": document_id,
                        "slide_number": slide_number,
                        "parent_chunk_id": slide_id,
                        "chunk_type_weight": 1.0
                    }
                )
                all_chunks.extend(bullet_chunks)
                
            # (2) 테이블
            IF shape.has_table:
                # 테이블 객체(.table)를 Markdown 등으로 변환하여 청킹
                table_chunks = chunk_pptx_table(
                    table=shape.table, # Table 객체 전달
                    config=config,
                    base_metadata={
                        "document_id": document_id,
                        "slide_number": slide_number,
                        "parent_chunk_id": slide_id,
                        "chunk_type_weight": 1.2
                    }
                )
                all_chunks.extend(table_chunks)
            
            # (3) 차트 (Chart), 스마트아트 (SmartArt) 등
            # (고급: 차트 데이터를 텍스트로 변환하거나, SmartArt의 텍스트를 추출)
            # IF shape.has_chart: ...
            
    RETURN all_chunks
2.2.4. 핵심 헬퍼 함수 (Helper Functions)
Python

FUNCTION chunk_bullet_points_by_level(text_frame, config, base_metadata):
    """
    (가장 중요) paragraph.level을 사용하여 불릿을 의미론적 그룹으로 묶습니다.
    전략: 최상위 불릿(level 0)과 그에 속한 하위 불릿(level > 0)들을 하나의 그룹으로 묶습니다.
    """
    chunks = []
    current_bullet_group_lines = [] # ['• 상위 1', '  - 하위 1.1', '  - 하위 1.2']
    
    # 1. TextFrame 내의 모든 문단(불릿)을 순회
    FOR paragraph IN text_frame.paragraphs:
        IF is_empty(paragraph.text):
            CONTINUE
            
        paragraph_text = f"{'  ' * paragraph.level}{paragraph.text}" # 들여쓰기 시각화
        indent_level = paragraph.level # 0, 1, 2...
        
        # 2. 새 최상위 불릿(level 0)이 시작되고, 버퍼에 내용이 있다면
        IF indent_level == 0 AND is_not_empty(current_bullet_group_lines):
            # 2a. 지금까지 모은 버퍼(이전 상위 불릿 그룹)를 하나의 텍스트로
            group_content = "\n".join(current_bullet_group_lines)
            
            # 2b. 이 그룹이 너무 크면 Fallback 적용
            group_chunks = chunk_element_with_fallback(
                content=group_content,
                type="bullet_group",
                config=config,
                base_metadata=base_metadata
            )
            chunks.extend(group_chunks)
            
            # 2c. 버퍼 비우고, 새 최상위 불릿으로 시작
            current_bullet_group_lines = [paragraph_text]
        ELSE:
            # 3. 하위 불릿이거나 첫 번째 상위 불릿이면, 버퍼에 계속 추가
            current_bullet_group_lines.append(paragraph_text)
            
    # 4. 루프 종료 후, 마지막 불릿 그룹 처리
    IF is_not_empty(current_bullet_group_lines):
        group_content = "\n".join(current_bullet_group_lines)
        group_chunks = chunk_element_with_fallback(
            content=group_content,
            type="bullet_group",
            config=config,
            base_metadata=base_metadata
        )
        chunks.extend(group_chunks)
        
    RETURN chunks

FUNCTION chunk_pptx_table(table, config, base_metadata):
    """
    python-pptx의 Table 객체를 RAG가 이해하기 쉬운 Markdown 텍스트로 변환 후 청킹.
    """
    markdown_lines = []
    
    # 1. 헤더 (첫 번째 행)
    header_cells = [cell.text for cell in table.rows[0].cells]
    markdown_lines.append(f"| {' | '.join(header_cells)} |")
    markdown_lines.append(f"| {' | '.join(['---'] * len(header_cells))} |")
    
    # 2. 본문 (나머지 행)
    FOR row IN table.rows[1:]:
        body_cells = [cell.text for cell in row.cells]
        markdown_lines.append(f"| {' | '.join(body_cells)} |")
        
    markdown_table = "\n".join(markdown_lines)
    
    # 3. 변환된 Markdown 텍스트가 너무 길면 Fallback 적용
    table_chunks = chunk_element_with_fallback(
        content=markdown_table,
        type="table",
        config=config,
        base_metadata=base_metadata
    )
    RETURN table_chunks

FUNCTION extract_full_text_from_slide_shapes(slide):
    """
    슬라이드 내의 모든 '보이는' 텍스트(제목, 본문, 표)를 추출하여
    '부모 청크'용 전체 텍스트를 반환합니다. (노트는 의도적으로 제외)
    """
    full_text = []
    
    # 1. 제목
    IF slide.shapes.title IS NOT None AND slide.shapes.title.has_text_frame:
        full_text.append(f"[제목]:\n{slide.shapes.title.text_frame.text}")
    
    # 2. 본문 및 기타 텍스트
    FOR shape IN slide.shapes:
        IF shape.is_placeholder AND shape.placeholder_format.type == "TITLE":
            CONTINUE # 제목 중복 방지
        
        IF shape.has_text_frame:
            full_text.append(f"[본문]:\n{shape.text_frame.text}")
        
        IF shape.has_table:
            # 테이블도 단순 텍스트로 변환하여 문맥에 포함
            table_text = convert_table_to_simple_text(shape.table)
            full_text.append(f"[표]:\n{table_text}")
            
    RETURN "\n\n".join(full_text)

# --- (PDF 전략과 공유되는 헬퍼 함수) ---
FUNCTION chunk_element_with_fallback(content, type, config, base_metadata):
    """
    (PDF 전략과 동일) 요소가 max_size를 초과할 경우 재귀적으로 분할합니다.
    """
    # ... (PDF 의사 코드와 동일한 로직) ...