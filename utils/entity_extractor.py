"""
LLM 기반 엔티티 추출기
화합물명, 수치, 측정값 등을 추출하여 검색 정확도 향상
"""
from typing import Dict, List, Any, Optional
import json
import re


class LLMEntityExtractor:
    """LLM을 사용하여 텍스트에서 엔티티를 추출"""
    
    def __init__(self, llm, entity_types: List[str] = None):
        """
        Args:
            llm: LangChain LLM 인스턴스
            entity_types: 추출할 엔티티 타입 리스트
        """
        self.llm = llm
        self.entity_types = entity_types or ["compound", "number", "measurement"]
        
        # 엔티티 추출 프롬프트 템플릿 (한국어 지원 강화)
        self.extraction_prompt = """다음 텍스트에서 엔티티를 추출하세요. 엔티티 타입을 키로 하고, 엔티티 리스트를 값으로 하는 JSON 객체를 반환하세요.

추출할 엔티티 타입:
- compounds: 화학 화합물, 재료, 약어 (예: TADF, ACRSA, DABNA1, HF, OLED, EQE, FRET, PLQY, DMAC-TRZ, AZB-TRZ, ν-DABNA)
- numbers: 수치 값과 맥락 (예: "30%", "3배 증가", "12.3%", "500", "1.5")
- measurements: 물리적 측정값 (예: "500nm", "25°C", "100mA", "3.5 ns", "500 eV")

텍스트:
"{text}"

요구사항:
1. 텍스트에 나타난 그대로 엔티티를 추출하세요
2. 수치는 맥락을 포함하세요 (예: "효율 30%" 단순히 "30"이 아님)
3. 측정값은 단위를 포함하세요
4. 화합물의 경우 전체 이름과 약어 모두 추출하세요
5. 유효한 JSON 객체만 반환하세요

출력 형식:
{{"compounds": ["entity1", "entity2"], "numbers": ["value1", "value2"], "measurements": ["measure1", "measure2"]}}

엔티티:"""
    
    def extract_entities(self, text: str, max_length: int = 500) -> Dict[str, List[str]]:
        """
        텍스트에서 엔티티 추출
        
        Args:
            text: 추출할 텍스트
            max_length: LLM에 보낼 최대 텍스트 길이
            
        Returns:
            엔티티 타입별 리스트 딕셔너리
        """
        if not text or len(text.strip()) == 0:
            return {entity_type: [] for entity_type in self.entity_types}
        
        # 텍스트 길이 제한 (성능 최적화)
        truncated_text = text[:max_length] if len(text) > max_length else text
        
        try:
            # LLM 호출
            prompt = self.extraction_prompt.format(text=truncated_text)
            response = self.llm.invoke(prompt)
            
            # 응답 파싱
            if hasattr(response, 'content'):
                response_text = response.content
            elif hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)
            
            # JSON 추출 및 파싱
            entities = self._parse_entities_from_response(response_text)
            
            # Fallback: 정규식 기반 추출
            if not entities or all(len(v) == 0 for v in entities.values()):
                entities = self._fallback_extraction(text)
            
            return entities
            
        except Exception as e:
            print(f"⚠️ LLM 엔티티 추출 실패: {e}")
            # Fallback: 정규식 기반 추출
            return self._fallback_extraction(text)
    
    def _parse_entities_from_response(self, response_text: str) -> Dict[str, List[str]]:
        """LLM 응답에서 엔티티 파싱"""
        try:
            # JSON 부분 추출
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                entities_dict = json.loads(json_match.group())
                
                # 엔티티 타입 검증 및 정제
                result = {}
                for entity_type in self.entity_types:
                    if entity_type in entities_dict:
                        # 리스트 형식 확인
                        if isinstance(entities_dict[entity_type], list):
                            # 중복 제거 및 정제
                            result[entity_type] = list(set([
                                e.strip() for e in entities_dict[entity_type] 
                                if e and len(e.strip()) > 0
                            ]))
                        else:
                            result[entity_type] = []
                    else:
                        result[entity_type] = []
                
                return result
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"엔티티 파싱 오류: {e}")
        
        return {entity_type: [] for entity_type in self.entity_types}
    
    def _fallback_extraction(self, text: str) -> Dict[str, List[str]]:
        """정규식 기반 Fallback 엔티티 추출"""
        entities = {entity_type: [] for entity_type in self.entity_types}
        
        # 화합물명 패턴 (대문자 약어, 하이픈 포함 이름) - 한국어 지원 강화
        compound_patterns = [
            r'\b[A-Z]{2,}(?:-[A-Z0-9]+)*\b',  # TADF, ACRSA, ACR-SA, DMAC-TRZ
            r'\b[A-Z][a-z]*[A-Z0-9]+\b',       # DABNA1, ν-DABNA
            r'\b[A-Z]+[0-9]+\b',               # AZB-TRZ 형식
            r'\bν-[A-Z0-9]+\b',                # ν-DABNA 등 그리스 문자 포함
        ]
        
        compounds = set()
        for pattern in compound_patterns:
            matches = re.findall(pattern, text)
            # 일반적인 영어 단어 제외 (예: THE, AND, OR 등)
            common_words = {"THE", "AND", "OR", "FOR", "WITH", "FROM", "THIS", "THAT", "ARE", "WAS"}
            compounds.update([m for m in matches if len(m) >= 2 and m not in common_words])
        
        entities["compounds"] = list(compounds)
        
        # 수치 패턴 (%, 배, 회 등 포함) - 한국어 및 영어 지원 강화
        number_patterns = [
            r'\d+\.?\d*\s*%',                  # 30%, 12.3%
            r'\d+\.?\d*\s*퍼센트',               # 30퍼센트
            r'\d+\.?\d*\s*배',                 # 3배, 1.5배
            r'\d+\.?\d*\s*회',                 # 10회
            r'\d+\.?\d*\s*(?:times|fold)',     # 3 times, 2 fold
            r'\d+\.?\d*\s*증가',               # 3배 증가
            r'\d+\.?\d*\s*감소',               # 30% 감소
            # 순수 숫자 패턴 (맥락이 필요한 경우)
            r'\b\d+\.\d+\b',                    # 소수점 포함 숫자
        ]
        
        numbers = set()
        for pattern in number_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            numbers.update(matches)
        
        # 순수 숫자도 추가 (단위나 맥락이 명확한 경우)
        pure_numbers = re.findall(r'\b\d+\.?\d+\b', text)
        # 매우 큰 숫자나 특별한 숫자는 제외 (예: 연도, 페이지 번호 등)
        for num in pure_numbers:
            try:
                num_val = float(num) if '.' in num else int(num)
                if 0.1 <= num_val <= 10000:  # 일반적인 측정값 범위
                    numbers.add(num)
            except:
                pass
        
        entities["numbers"] = list(numbers)
        
        # 측정값 패턴 (단위 포함) - 확장
        measurement_patterns = [
            r'\d+\.?\d*\s*(?:nm|μm|mm|cm|m|km)',       # 길이
            r'\d+\.?\d*\s*(?:°C|℃|°F|℉|K)',            # 온도
            r'\d+\.?\d*\s*(?:mA|A|V|W|mW|kW)',         # 전기
            r'\d+\.?\d*\s*(?:g|mg|kg|mol)',            # 질량/물질량
            r'\d+\.?\d*\s*(?:Hz|kHz|MHz|GHz)',         # 주파수
            r'\d+\.?\d*\s*ns',                         # 나노초 (3.5 ns)
            r'\d+\.?\d*\s*(?:eV|keV|MeV)',             # 에너지
            r'\d+\.?\d*\s*(?:μL|mL|L)',                # 부피
        ]
        
        measurements = set()
        for pattern in measurement_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            measurements.update(matches)
        
        entities["measurements"] = list(measurements)
        
        return entities
    
    def create_entity_index(self, chunks: List[Any]) -> Dict[str, Dict[str, List[str]]]:
        """
        청크들에서 엔티티 인덱스 생성
        
        Args:
            chunks: Chunk 객체 리스트 또는 Document 객체 리스트
            
        Returns:
            chunk_id -> entities 매핑
        """
        entity_index = {}
        
        for i, chunk in enumerate(chunks):
            # chunk_id 추출
            if hasattr(chunk, 'id'):
                chunk_id = chunk.id
            elif hasattr(chunk, 'metadata') and 'chunk_id' in chunk.metadata:
                chunk_id = chunk.metadata['chunk_id']
            else:
                chunk_id = f"chunk_{i}"
            
            # 텍스트 추출
            if hasattr(chunk, 'content'):
                text = chunk.content
            elif hasattr(chunk, 'page_content'):
                text = chunk.page_content
            else:
                continue
            
            # 엔티티 추출 (배치 처리 시 작은 텍스트만)
            if len(text) > 100:  # 최소 길이 확인
                entities = self.extract_entities(text, max_length=500)
                
                # 엔티티가 있는 경우만 인덱스에 추가
                if any(len(v) > 0 for v in entities.values()):
                    entity_index[chunk_id] = entities
        
        print(f"✅ 엔티티 인덱스 생성 완료: {len(entity_index)}개 청크")
        return entity_index
    
    def batch_extract_entities(self, chunks: List[Any], batch_size: int = 10) -> Dict[str, Dict[str, List[str]]]:
        """
        배치 단위로 엔티티 추출 (성능 최적화)
        
        Args:
            chunks: Chunk 객체 리스트
            batch_size: 배치 크기
            
        Returns:
            chunk_id -> entities 매핑
        """
        entity_index = {}
        total = len(chunks)
        
        for i in range(0, total, batch_size):
            batch = chunks[i:i+batch_size]
            print(f"엔티티 추출 중: {i+1}-{min(i+batch_size, total)}/{total}")
            
            for chunk in batch:
                # chunk_id 추출
                if hasattr(chunk, 'id'):
                    chunk_id = chunk.id
                else:
                    chunk_id = f"chunk_{i}"
                
                # 텍스트 추출
                if hasattr(chunk, 'content'):
                    text = chunk.content
                elif hasattr(chunk, 'page_content'):
                    text = chunk.page_content
                else:
                    continue
                
                # 엔티티 추출
                if len(text) > 100:
                    entities = self.extract_entities(text, max_length=500)
                    
                    if any(len(v) > 0 for v in entities.values()):
                        entity_index[chunk_id] = entities
        
        print(f"✅ 배치 엔티티 추출 완료: {len(entity_index)}개 청크")
        return entity_index

