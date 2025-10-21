# 구조 인식 청킹 전략 개발문서

## 📋 개요

이 문서는 PDF, PPT/PPTX, XLS/XLSX, Text 4가지 문서 타입에 대한 구조 인식 청킹 전략을 정의합니다. 각 문서 타입의 고유한 구조를 분석하여 의미론적으로 응집된 청크를 생성하는 방법을 제시합니다.

## 🎯 목표

- 문서의 구조적 정보를 보존하는 청킹
- 의미론적 응집성 향상
- 검색 정확도 및 관련성 개선
- 문서 타입별 최적화된 청킹 전략

---

## 1. PDF 문서 구조 인식 청킹

### PDF 구조 분석
```python
def analyze_pdf_structure(pdf_content):
    """PDF 문서의 구조를 분석"""
    structure = {
        "titles": [],      # 제목들 (크기별)
        "sections": [],    # 섹션 구분자
        "paragraphs": [],  # 문단들
        "lists": [],       # 리스트 항목들
        "tables": [],      # 표 데이터
        "code_blocks": []  # 코드 블록
    }
    
    # 1. 제목 패턴 인식 (크기별)
    title_patterns = [
        r'^#+\s+(.+)$',           # Markdown 스타일
        r'^제?\d+[장절]\s+(.+)$',  # 한국어 장절
        r'^\d+\.\d*\s+(.+)$',     # 번호 제목
        r'^[A-Z][A-Z\s]+$',       # 대문자 제목
    ]
    
    # 2. 섹션 구분자 인식
    section_patterns = [
        r'^={3,}$',               # 등호 구분선
        r'^-{3,}$',                # 대시 구분선
        r'^\*{3,}$',               # 별표 구분선
    ]
    
    # 3. 문단 구분 (빈 줄 기준)
    paragraphs = pdf_content.split('\n\n')
    
    return structure
```

### PDF 청킹 전략
```python
def pdf_structure_aware_chunking(pdf_content, max_size=500):
    """PDF 문서 구조를 인식한 청킹"""
    chunks = []
    
    # 1단계: 섹션 단위 분할
    sections = split_by_sections(pdf_content)
    
    for section in sections:
        if len(section) <= max_size:
            chunks.append({
                "content": section,
                "chunk_type": "section",
                "metadata": extract_section_metadata(section)
            })
        else:
            # 2단계: 문단 단위 재분할
            paragraphs = section.split('\n\n')
            current_chunk = ""
            chunk_type = "paragraph"
            
            for para in paragraphs:
                para_type = classify_paragraph_type(para)
                
                if len(current_chunk + para) <= max_size:
                    current_chunk += para + "\n\n"
                    chunk_type = para_type  # 마지막 문단 타입으로 설정
                else:
                    if current_chunk:
                        chunks.append({
                            "content": current_chunk.strip(),
                            "chunk_type": chunk_type,
                            "metadata": extract_chunk_metadata(current_chunk)
                        })
                    current_chunk = para + "\n\n"
                    chunk_type = para_type
            
            if current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "chunk_type": chunk_type,
                    "metadata": extract_chunk_metadata(current_chunk)
                })
    
    return chunks

def classify_paragraph_type(paragraph):
    """문단 유형 분류"""
    if re.search(r'^#+\s', paragraph):  # 제목
        return "title"
    elif re.search(r'^\d+\.|^[-*]', paragraph):  # 리스트
        return "list"
    elif re.search(r'```|`[^`]+`', paragraph):  # 코드
        return "code"
    elif re.search(r'\|.*\|', paragraph):  # 표
        return "table"
    elif len(paragraph.split()) <= 10:  # 짧은 문단 (제목 가능성)
        return "subtitle"
    else:
        return "paragraph"
```

---

## 2. PPT/PPTX 문서 구조 인식 청킹

### PPTX 구조 분석
```python
def analyze_pptx_structure(pptx_content):
    """PPTX 문서의 구조를 분석"""
    structure = {
        "slides": [],           # 슬라이드별 내용
        "slide_titles": [],     # 슬라이드 제목들
        "slide_notes": [],       # 슬라이드 노트
        "bullet_points": [],    # 불릿 포인트들
        "images": [],           # 이미지 설명
        "tables": [],           # 표 데이터
        "charts": []            # 차트 설명
    }
    
    # 슬라이드별 분할 (페이지 번호 기준)
    slides = split_by_slides(pptx_content)
    
    for slide_num, slide_content in enumerate(slides):
        slide_structure = {
            "slide_number": slide_num + 1,
            "title": extract_slide_title(slide_content),
            "content": extract_slide_content(slide_content),
            "notes": extract_slide_notes(slide_content),
            "bullet_points": extract_bullet_points(slide_content),
            "tables": extract_tables(slide_content),
            "images": extract_image_descriptions(slide_content)
        }
        structure["slides"].append(slide_structure)
    
    return structure
```

### PPTX 청킹 전략
```python
def pptx_structure_aware_chunking(pptx_content, max_size=300):
    """PPTX 문서 구조를 인식한 청킹 (슬라이드 단위 우선)"""
    chunks = []
    
    # 1단계: 슬라이드별 분할
    slides = split_by_slides(pptx_content)
    
    for slide_num, slide_content in enumerate(slides):
        slide_chunks = []
        
        # 슬라이드 제목 (별도 청크)
        title = extract_slide_title(slide_content)
        if title and len(title) <= max_size:
            slide_chunks.append({
                "content": title,
                "chunk_type": "slide_title",
                "metadata": {
                    "slide_number": slide_num + 1,
                    "weight": 2.0  # 제목은 가중치 높게
                }
            })
        
        # 슬라이드 본문 내용
        main_content = extract_slide_content(slide_content)
        if main_content:
            if len(main_content) <= max_size:
                slide_chunks.append({
                    "content": main_content,
                    "chunk_type": "slide_content",
                    "metadata": {
                        "slide_number": slide_num + 1,
                        "weight": 1.0
                    }
                })
            else:
                # 불릿 포인트별로 분할
                bullet_chunks = split_by_bullet_points(main_content, max_size)
                slide_chunks.extend(bullet_chunks)
        
        # 슬라이드 노트 (별도 청크)
        notes = extract_slide_notes(slide_content)
        if notes and len(notes) <= max_size:
            slide_chunks.append({
                "content": notes,
                "chunk_type": "slide_notes",
                "metadata": {
                    "slide_number": slide_num + 1,
                    "weight": 1.5  # 노트는 가중치 중간
                }
            })
        
        chunks.extend(slide_chunks)
    
    return chunks

def split_by_bullet_points(content, max_size):
    """불릿 포인트별로 분할"""
    chunks = []
    
    # 불릿 포인트 패턴
    bullet_patterns = [
        r'^[-*•]\s+(.+)$',        # 기본 불릿
        r'^\d+\.\s+(.+)$',        # 번호 리스트
        r'^[a-z]\.\s+(.+)$',      # 소문자 리스트
    ]
    
    bullet_points = []
    for pattern in bullet_patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        bullet_points.extend(matches)
    
    current_chunk = ""
    for bullet in bullet_points:
        if len(current_chunk + bullet) <= max_size:
            current_chunk += bullet + "\n"
        else:
            if current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "chunk_type": "bullet_list",
                    "metadata": {"weight": 1.2}
                })
            current_chunk = bullet + "\n"
    
    if current_chunk:
        chunks.append({
            "content": current_chunk.strip(),
            "chunk_type": "bullet_list",
            "metadata": {"weight": 1.2}
        })
    
    return chunks
```

---

## 3. XLS/XLSX 문서 구조 인식 청킹

### XLSX 구조 분석
```python
def analyze_xlsx_structure(xlsx_content):
    """XLSX 문서의 구조를 분석"""
    structure = {
        "worksheets": [],         # 워크시트별 데이터
        "headers": [],            # 헤더 행들
        "data_rows": [],          # 데이터 행들
        "formulas": [],           # 수식들
        "charts": [],             # 차트 설명
        "pivot_tables": []       # 피벗 테이블
    }
    
    # 워크시트별 분할
    worksheets = split_by_worksheets(xlsx_content)
    
    for ws_name, ws_content in worksheets.items():
        ws_structure = {
            "worksheet_name": ws_name,
            "headers": extract_headers(ws_content),
            "data_rows": extract_data_rows(ws_content),
            "formulas": extract_formulas(ws_content),
            "summary": extract_worksheet_summary(ws_content)
        }
        structure["worksheets"].append(ws_structure)
    
    return structure
```

### XLSX 청킹 전략
```python
def xlsx_structure_aware_chunking(xlsx_content, max_size=400):
    """XLSX 문서 구조를 인식한 청킹 (테이블 중심)"""
    chunks = []
    
    # 1단계: 워크시트별 분할
    worksheets = split_by_worksheets(xlsx_content)
    
    for ws_name, ws_content in worksheets.items():
        # 워크시트 헤더 (별도 청크)
        headers = extract_headers(ws_content)
        if headers:
            header_text = f"워크시트: {ws_name}\n헤더: {headers}"
            chunks.append({
                "content": header_text,
                "chunk_type": "worksheet_header",
                "metadata": {
                    "worksheet_name": ws_name,
                    "weight": 2.0
                }
            })
        
        # 데이터 행들을 그룹으로 청킹
        data_rows = extract_data_rows(ws_content)
        if data_rows:
            row_groups = group_rows_by_size(data_rows, max_size)
            
            for group_num, row_group in enumerate(row_groups):
                group_text = f"워크시트: {ws_name}\n데이터 그룹 {group_num + 1}:\n"
                group_text += "\n".join([format_row(row) for row in row_group])
                
                chunks.append({
                    "content": group_text,
                    "chunk_type": "data_group",
                    "metadata": {
                        "worksheet_name": ws_name,
                        "group_number": group_num + 1,
                        "row_count": len(row_group),
                        "weight": 1.0
                    }
                })
        
        # 수식 설명 (별도 청크)
        formulas = extract_formulas(ws_content)
        if formulas:
            formula_text = f"워크시트: {ws_name}\n수식들:\n" + "\n".join(formulas)
            chunks.append({
                "content": formula_text,
                "chunk_type": "formulas",
                "metadata": {
                    "worksheet_name": ws_name,
                    "weight": 1.5
                }
            })
    
    return chunks

def group_rows_by_size(rows, max_size):
    """행들을 크기에 맞게 그룹화"""
    groups = []
    current_group = []
    current_size = 0
    
    for row in rows:
        row_text = format_row(row)
        row_size = len(row_text)
        
        if current_size + row_size <= max_size:
            current_group.append(row)
            current_size += row_size
        else:
            if current_group:
                groups.append(current_group)
            current_group = [row]
            current_size = row_size
    
    if current_group:
        groups.append(current_group)
    
    return groups
```

---

## 4. Text 문서 구조 인식 청킹

### Text 구조 분석
```python
def analyze_text_structure(text_content):
    """Text 문서의 구조를 분석"""
    structure = {
        "paragraphs": [],        # 문단들
        "sections": [],          # 섹션들
        "lists": [],             # 리스트들
        "code_blocks": [],       # 코드 블록들
        "headers": []            # 헤더들
    }
    
    # 1. 헤더 패턴 인식
    header_patterns = [
        r'^#+\s+(.+)$',           # Markdown 헤더
        r'^제?\d+[장절]\s+(.+)$',  # 한국어 장절
        r'^\d+\.\d*\s+(.+)$',     # 번호 헤더
        r'^[A-Z][A-Z\s]+$',       # 대문자 헤더
    ]
    
    # 2. 섹션 구분자
    section_separators = [
        r'^={3,}$',               # 등호 구분선
        r'^-{3,}$',               # 대시 구분선
        r'^\*{3,}$',              # 별표 구분선
    ]
    
    # 3. 코드 블록
    code_patterns = [
        r'```[\s\S]*?```',        # Markdown 코드 블록
        r'`[^`]+`',               # 인라인 코드
    ]
    
    return structure
```

### Text 청킹 전략
```python
def text_structure_aware_chunking(text_content, max_size=500):
    """Text 문서 구조를 인식한 청킹"""
    chunks = []
    
    # 1단계: 섹션 단위 분할
    sections = split_by_sections(text_content)
    
    for section in sections:
        if len(section) <= max_size:
            chunks.append({
                "content": section,
                "chunk_type": "section",
                "metadata": extract_section_metadata(section)
            })
        else:
            # 2단계: 문단 단위 재분할
            paragraphs = section.split('\n\n')
            current_chunk = ""
            chunk_type = "paragraph"
            
            for para in paragraphs:
                para_type = classify_text_paragraph_type(para)
                
                if len(current_chunk + para) <= max_size:
                    current_chunk += para + "\n\n"
                    chunk_type = para_type
                else:
                    if current_chunk:
                        chunks.append({
                            "content": current_chunk.strip(),
                            "chunk_type": chunk_type,
                            "metadata": extract_chunk_metadata(current_chunk)
                        })
                    current_chunk = para + "\n\n"
                    chunk_type = para_type
            
            if current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "chunk_type": chunk_type,
                    "metadata": extract_chunk_metadata(current_chunk)
                })
    
    return chunks

def classify_text_paragraph_type(paragraph):
    """Text 문단 유형 분류"""
    if re.search(r'^#+\s', paragraph):  # Markdown 헤더
        return "header"
    elif re.search(r'```[\s\S]*?```', paragraph):  # 코드 블록
        return "code_block"
    elif re.search(r'`[^`]+`', paragraph):  # 인라인 코드
        return "inline_code"
    elif re.search(r'^\d+\.|^[-*]', paragraph):  # 리스트
        return "list"
    elif re.search(r'\|.*\|', paragraph):  # 표
        return "table"
    elif len(paragraph.split()) <= 5:  # 짧은 문단 (헤더 가능성)
        return "subheader"
    else:
        return "paragraph"
```

---

## 📋 구현 가이드라인

### 공통 메타데이터 구조
```python
def extract_chunk_metadata(chunk_content):
    """청크 메타데이터 추출"""
    return {
        "word_count": len(chunk_content.split()),
        "char_count": len(chunk_content),
        "has_code": bool(re.search(r'```|`[^`]+`', chunk_content)),
        "has_table": bool(re.search(r'\|.*\|', chunk_content)),
        "has_list": bool(re.search(r'^\d+\.|^[-*]', chunk_content)),
        "has_formula": bool(re.search(r'[=+\-*/]', chunk_content)),
        "language": detect_language(chunk_content),
        "created_at": datetime.now().isoformat()
    }
```

### 가중치 시스템
```python
CHUNK_TYPE_WEIGHTS = {
    "title": 2.0,           # 제목
    "slide_title": 2.0,     # 슬라이드 제목
    "worksheet_header": 2.0, # 워크시트 헤더
    "header": 1.8,          # 헤더
    "slide_notes": 1.5,     # 슬라이드 노트
    "formulas": 1.5,        # 수식
    "code_block": 1.3,     # 코드 블록
    "bullet_list": 1.2,    # 불릿 리스트
    "data_group": 1.0,     # 데이터 그룹
    "paragraph": 1.0,      # 일반 문단
    "section": 1.0         # 섹션
}
```

### 문서 타입별 최적 청크 크기
```python
OPTIMAL_CHUNK_SIZES = {
    "pdf": 500,      # 일반적인 문서 크기
    "pptx": 300,     # 슬라이드 단위로 작게
    "xlsx": 400,     # 테이블 데이터 고려
    "txt": 500       # 일반 텍스트
}
```

---

## 🎯 프로젝트 적용 계획

### 1단계: 기본 구조 구현
- 각 문서 타입별 청킹 함수 구현
- 메타데이터 추출 시스템 구축
- 가중치 시스템 적용

### 2단계: 통합 시스템
- `document_processor.py`에 통합
- 기존 청킹 로직과 호환성 확보
- 설정 파일에 청킹 전략 옵션 추가

### 3단계: 최적화
- 성능 테스트 및 튜닝
- 사용자 피드백 반영
- 추가 문서 타입 지원 확장

---

## 📚 참고사항

- 이 문서는 상용 RAG 시스템들의 청킹 전략을 분석하여 작성되었습니다.
- 각 문서 타입의 고유한 특성을 최대한 활용하여 의미론적 응집성을 높입니다.
- 구현 시 기존 시스템과의 호환성을 유지해야 합니다.
- 성능 테스트를 통해 최적의 청크 크기와 가중치를 조정해야 합니다.

---

**문서 버전**: 1.0  
**최종 수정일**: 2024-12-19  
**작성자**: RAG Development Team
