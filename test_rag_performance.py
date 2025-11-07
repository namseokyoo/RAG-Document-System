"""
RAG 성능 테스트 스크립트
- 기존 임베딩 제거 및 테스트 문서 임베딩
- Reference 결과와 비교하여 성능 평가
- 세션 내 주제 변경 테스트 포함
"""

import os
import json
import shutil
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from config import ConfigManager
from utils.vector_store import VectorStoreManager
from utils.document_processor import DocumentProcessor
from utils.rag_chain import RAGChain
from utils.chat_history import ChatHistoryManager


class RAGPerformanceTester:
    """RAG 성능 테스트 클래스"""
    
    def __init__(self, config_path: str = "config.json"):
        """초기화"""
        config_manager = ConfigManager()
        self.config = config_manager.config
        self.results = []
        self.test_start_time = None
        
        # 디렉토리 설정
        self.test_docs_dir = Path("data/test_documents")
        self.test_pptx_dir = Path("data/test_pptx")
        self.reference_pdf_path = self.test_docs_dir / "reference_result.json"
        self.reference_pptx_path = self.test_pptx_dir / "reference_result.json"
        self.output_dir = Path("test_results")
        self.output_dir.mkdir(exist_ok=True)
        
    def setup_test_environment(self, clear_existing: bool = True) -> bool:
        """테스트 환경 준비"""
        print("\n" + "="*80)
        print("📋 Phase 1: 테스트 환경 준비")
        print("="*80)
        
        try:
            # 1. 기존 임베딩 제거 (개별 문서 삭제 방식)
            if clear_existing:
                print("\n[1/3] 기존 임베딩 제거 중...")
                try:
                    # 임시 VectorStore로 기존 문서 목록 확인
                    temp_vector_store = VectorStoreManager(
                        persist_directory="data/chroma_db",
                        embedding_api_type=self.config.get("embedding_api_type", "request"),
                        embedding_base_url=self.config.get("embedding_base_url", "http://localhost:11434"),
                        embedding_model=self.config.get("embedding_model", "mxbai-embed-large:latest"),
                        embedding_api_key=self.config.get("embedding_api_key", "")
                    )
                    existing_docs = temp_vector_store.get_documents_list()
                    if existing_docs:
                        print(f"  기존 문서 {len(existing_docs)}개 발견, 개별 삭제 중...")
                        for doc in existing_docs:
                            try:
                                temp_vector_store.delete_document(doc['file_name'])
                                print(f"    - {doc['file_name']} 삭제 완료")
                            except Exception as e:
                                print(f"    - {doc['file_name']} 삭제 실패: {e}")
                        print(f"✅ 기존 문서 삭제 완료")
                    else:
                        print(f"ℹ️  기존 문서가 없습니다")
                except Exception as e:
                    print(f"⚠️  기존 문서 삭제 중 오류 (계속 진행): {e}")
            
            # 2. VectorStore 초기화
            print("\n[2/3] VectorStore 초기화 중...")
            self.vector_store = VectorStoreManager(
                persist_directory="data/chroma_db",
                embedding_api_type=self.config.get("embedding_api_type", "request"),
                embedding_base_url=self.config.get("embedding_base_url", "http://localhost:11434"),
                embedding_model=self.config.get("embedding_model", "mxbai-embed-large:latest"),
                embedding_api_key=self.config.get("embedding_api_key", "")
            )
            print("✅ VectorStore 초기화 완료")
            
            # 3. DocumentProcessor 초기화
            print("\n[3/3] DocumentProcessor 초기화 중...")
            self.document_processor = DocumentProcessor(
                chunk_size=self.config.get("chunk_size", 1500),
                chunk_overlap=self.config.get("chunk_overlap", 400),
                enable_advanced_pdf_chunking=True,
                enable_advanced_pptx_chunking=True
            )
            print("✅ DocumentProcessor 초기화 완료")
            
            return True
            
        except Exception as e:
            print(f"❌ 환경 준비 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def embed_test_documents(self) -> bool:
        """테스트 문서 임베딩"""
        print("\n" + "="*80)
        print("📚 Phase 2: 테스트 문서 임베딩")
        print("="*80)
        
        try:
            # PDF 문서 임베딩
            print("\n[1/2] PDF 문서 임베딩 중...")
            pdf_files = list(self.test_docs_dir.glob("*.pdf"))
            pdf_files = [f for f in pdf_files if f.name != "reference_result.json"]
            
            if not pdf_files:
                print("⚠️  PDF 파일을 찾을 수 없습니다")
                return False
            
            print(f"📄 PDF 파일 {len(pdf_files)}개 발견")
            for pdf_file in pdf_files:
                print(f"  - {pdf_file.name}")
            
            for pdf_file in pdf_files:
                try:
                    print(f"\n📄 임베딩 중: {pdf_file.name}")
                    file_type = self.document_processor.get_file_type(pdf_file.name)
                    chunks = self.document_processor.process_document(
                        str(pdf_file), pdf_file.name, file_type
                    )
                    if chunks:
                        # 벡터스토어에 추가
                        success = self.vector_store.add_documents(chunks)
                        if success:
                            print(f"  ✅ 성공: {len(chunks)}개 청크 생성 및 임베딩 완료")
                        else:
                            print(f"  ❌ 실패: 벡터스토어 추가 실패")
                    else:
                        print(f"  ❌ 실패: 청크 생성 실패")
                except Exception as e:
                    print(f"  ❌ 오류: {e}")
                    import traceback
                    traceback.print_exc()
            
            # PPTX 문서 임베딩
            print("\n[2/2] PPTX 문서 임베딩 중...")
            pptx_files = list(self.test_pptx_dir.glob("*.pptx"))
            pptx_files = [f for f in pptx_files if f.name != "reference_result.json"]
            
            if not pptx_files:
                print("⚠️  PPTX 파일을 찾을 수 없습니다")
                return False
            
            print(f"📊 PPTX 파일 {len(pptx_files)}개 발견")
            for pptx_file in pptx_files:
                print(f"  - {pptx_file.name}")
            
            for pptx_file in pptx_files:
                try:
                    print(f"\n📊 임베딩 중: {pptx_file.name}")
                    file_type = self.document_processor.get_file_type(pptx_file.name)
                    chunks = self.document_processor.process_document(
                        str(pptx_file), pptx_file.name, file_type
                    )
                    if chunks:
                        # 벡터스토어에 추가
                        success = self.vector_store.add_documents(chunks)
                        if success:
                            print(f"  ✅ 성공: {len(chunks)}개 청크 생성 및 임베딩 완료")
                        else:
                            print(f"  ❌ 실패: 벡터스토어 추가 실패")
                    else:
                        print(f"  ❌ 실패: 청크 생성 실패")
                except Exception as e:
                    print(f"  ❌ 오류: {e}")
                    import traceback
                    traceback.print_exc()
            
            # 임베딩 검증
            print("\n[검증] 임베딩된 문서 확인 중...")
            documents = self.vector_store.get_documents_list()
            print(f"✅ 총 {len(documents)}개 문서 임베딩 완료")
            for doc in documents:
                print(f"  - {doc['file_name']} ({doc['chunk_count']}개 청크)")
            
            return True
            
        except Exception as e:
            print(f"❌ 문서 임베딩 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_reference_results(self) -> tuple:
        """Reference 결과 로드"""
        pdf_ref = []
        pptx_ref = []
        
        try:
            if self.reference_pdf_path.exists():
                with open(self.reference_pdf_path, 'r', encoding='utf-8') as f:
                    pdf_ref = json.load(f)
                print(f"✅ PDF Reference 결과 로드: {len(pdf_ref)}개 질문")
        except Exception as e:
            print(f"⚠️  PDF Reference 결과 로드 실패: {e}")
        
        try:
            if self.reference_pptx_path.exists():
                with open(self.reference_pptx_path, 'r', encoding='utf-8') as f:
                    pptx_ref = json.load(f)
                print(f"✅ PPTX Reference 결과 로드: {len(pptx_ref)}개 질문")
        except Exception as e:
            print(f"⚠️  PPTX Reference 결과 로드 실패: {e}")
        
        return pdf_ref, pptx_ref
    
    def test_pdf_documents(self, reference_results: List[Dict]) -> List[Dict]:
        """PDF 문서 테스트"""
        print("\n" + "="*80)
        print("📄 Phase 3: PDF 문서 테스트")
        print("="*80)
        
        # RAGChain 초기화
        rag_chain = RAGChain(
            vectorstore=self.vector_store,
            llm_api_type=self.config.get("llm_api_type", "request"),
            llm_base_url=self.config.get("llm_base_url", "http://localhost:11434"),
            llm_model=self.config.get("llm_model", "gemma3:latest"),
            llm_api_key=self.config.get("llm_api_key", ""),
            temperature=self.config.get("temperature", 0.3),
            top_k=self.config.get("top_k", 5),
            use_reranker=self.config.get("use_reranker", True),
            reranker_model=self.config.get("reranker_model", "multilingual-mini"),
            reranker_initial_k=self.config.get("reranker_initial_k", 40),
            enable_synonym_expansion=self.config.get("enable_synonym_expansion", True),
            enable_multi_query=self.config.get("enable_multi_query", False),
            multi_query_num=self.config.get("multi_query_num", 0)
        )
        
        results = []
        total = len(reference_results)
        
        print(f"\n📊 총 {total}개 질문 테스트 시작\n")
        
        for idx, ref_item in enumerate(reference_results, 1):
            question = ref_item.get("질문", ref_item.get("question", ""))
            expected_answer = ref_item.get("답변", ref_item.get("answer", ""))
            expected_sources = ref_item.get("출처", ref_item.get("sources", []))
            
            if not question:
                continue
            
            print(f"[{idx}/{total}] 질문: {question[:60]}...")
            
            try:
                start_time = time.perf_counter()
                
                # RAG 쿼리 실행
                result = rag_chain.query(question, chat_history=[])
                
                elapsed_time = time.perf_counter() - start_time
                
                answer = result.get("answer", "")
                sources = result.get("sources", [])
                confidence = result.get("confidence", 0.0)
                success = result.get("success", False)
                
                # 결과 저장
                test_result = {
                    "question": question,
                    "expected_answer": expected_answer,
                    "expected_sources": expected_sources,
                    "actual_answer": answer,
                    "actual_sources": sources,
                    "confidence": confidence,
                    "success": success,
                    "elapsed_time": elapsed_time,
                    "question_type": "pdf",
                    "question_index": idx
                }
                
                results.append(test_result)
                
                if success:
                    print(f"  ✅ 성공 ({elapsed_time:.2f}초, 신뢰도: {confidence:.2f})")
                else:
                    print(f"  ❌ 실패 ({elapsed_time:.2f}초)")
                
            except Exception as e:
                print(f"  ❌ 오류: {e}")
                results.append({
                    "question": question,
                    "error": str(e),
                    "question_type": "pdf",
                    "question_index": idx
                })
        
        return results
    
    def test_pptx_documents(self, reference_results: List[Dict]) -> List[Dict]:
        """PPTX 문서 테스트"""
        print("\n" + "="*80)
        print("📊 Phase 4: PPTX 문서 테스트")
        print("="*80)
        
        # RAGChain 초기화
        rag_chain = RAGChain(
            vectorstore=self.vector_store,
            llm_api_type=self.config.get("llm_api_type", "request"),
            llm_base_url=self.config.get("llm_base_url", "http://localhost:11434"),
            llm_model=self.config.get("llm_model", "gemma3:latest"),
            llm_api_key=self.config.get("llm_api_key", ""),
            temperature=self.config.get("temperature", 0.3),
            top_k=self.config.get("top_k", 5),
            use_reranker=self.config.get("use_reranker", True),
            reranker_model=self.config.get("reranker_model", "multilingual-mini"),
            reranker_initial_k=self.config.get("reranker_initial_k", 40),
            enable_synonym_expansion=self.config.get("enable_synonym_expansion", True),
            enable_multi_query=self.config.get("enable_multi_query", False),
            multi_query_num=self.config.get("multi_query_num", 0)
        )
        
        results = []
        total = len(reference_results)
        
        print(f"\n📊 총 {total}개 질문 테스트 시작\n")
        
        for idx, ref_item in enumerate(reference_results, 1):
            question = ref_item.get("question", ref_item.get("질문", ""))
            expected_answer = ref_item.get("answer", ref_item.get("답변", ""))
            expected_sources = ref_item.get("sources", ref_item.get("출처", []))
            
            if not question:
                continue
            
            print(f"[{idx}/{total}] 질문: {question[:60]}...")
            
            try:
                start_time = time.perf_counter()
                
                # RAG 쿼리 실행
                result = rag_chain.query(question, chat_history=[])
                
                elapsed_time = time.perf_counter() - start_time
                
                answer = result.get("answer", "")
                sources = result.get("sources", [])
                confidence = result.get("confidence", 0.0)
                success = result.get("success", False)
                
                # 결과 저장
                test_result = {
                    "question": question,
                    "expected_answer": expected_answer,
                    "expected_sources": expected_sources,
                    "actual_answer": answer,
                    "actual_sources": sources,
                    "confidence": confidence,
                    "success": success,
                    "elapsed_time": elapsed_time,
                    "question_type": "pptx",
                    "question_index": idx
                }
                
                results.append(test_result)
                
                if success:
                    print(f"  ✅ 성공 ({elapsed_time:.2f}초, 신뢰도: {confidence:.2f})")
                else:
                    print(f"  ❌ 실패 ({elapsed_time:.2f}초)")
                
            except Exception as e:
                print(f"  ❌ 오류: {e}")
                results.append({
                    "question": question,
                    "error": str(e),
                    "question_type": "pptx",
                    "question_index": idx
                })
        
        return results
    
    def test_topic_switching(self) -> List[Dict]:
        """세션 내 주제 변경 테스트"""
        print("\n" + "="*80)
        print("🔄 Phase 5: 세션 내 주제 변경 테스트")
        print("="*80)
        
        # RAGChain 초기화
        rag_chain = RAGChain(
            vectorstore=self.vector_store,
            llm_api_type=self.config.get("llm_api_type", "request"),
            llm_base_url=self.config.get("llm_base_url", "http://localhost:11434"),
            llm_model=self.config.get("llm_model", "gemma3:latest"),
            llm_api_key=self.config.get("llm_api_key", ""),
            temperature=self.config.get("temperature", 0.3),
            top_k=self.config.get("top_k", 5),
            use_reranker=self.config.get("use_reranker", True),
            reranker_model=self.config.get("reranker_model", "multilingual-mini"),
            reranker_initial_k=self.config.get("reranker_initial_k", 40),
            enable_synonym_expansion=self.config.get("enable_synonym_expansion", True),
            enable_multi_query=self.config.get("enable_multi_query", False),
            multi_query_num=self.config.get("multi_query_num", 0)
        )
        
        results = []
        
        # 테스트 시나리오: 주제 전환
        test_scenarios = [
            {
                "name": "OLED 주제 → 프로젝트 주제",
                "questions": [
                    "OLED 효율 향상 방법은?",
                    "프로젝트 계획서의 3가지 주요 목표는 무엇인가요?"
                ]
            },
            {
                "name": "프로젝트 주제 → OLED 주제",
                "questions": [
                    "프로젝트 예산은 얼마인가요?",
                    "MIPS란 무엇인가?"
                ]
            },
            {
                "name": "동일 주제 연속 질문",
                "questions": [
                    "OLED 효율은?",
                    "OLED 효율 향상 방법은?",
                    "OLED 효율 측정 방법은?"
                ]
            }
        ]
        
        print(f"\n📊 총 {len(test_scenarios)}개 시나리오 테스트 시작\n")
        
        chat_history = []
        
        for scenario_idx, scenario in enumerate(test_scenarios, 1):
            print(f"\n[시나리오 {scenario_idx}] {scenario['name']}")
            print("-" * 80)
            
            for q_idx, question in enumerate(scenario['questions'], 1):
                print(f"\n  질문 {q_idx}: {question}")
                
                try:
                    start_time = time.perf_counter()
                    
                    # RAG 쿼리 실행 (채팅 이력 포함)
                    result = rag_chain.query(question, chat_history=chat_history)
                    
                    elapsed_time = time.perf_counter() - start_time
                    
                    answer = result.get("answer", "")
                    sources = result.get("sources", [])
                    confidence = result.get("confidence", 0.0)
                    success = result.get("success", False)
                    
                    # 채팅 이력 업데이트
                    chat_history.append({"role": "user", "content": question})
                    chat_history.append({"role": "assistant", "content": answer})
                    
                    # 결과 저장
                    test_result = {
                        "scenario": scenario['name'],
                        "question": question,
                        "question_index_in_scenario": q_idx,
                        "actual_answer": answer,
                        "actual_sources": sources,
                        "confidence": confidence,
                        "success": success,
                        "elapsed_time": elapsed_time,
                        "question_type": "topic_switching",
                        "chat_history_length": len(chat_history)
                    }
                    
                    results.append(test_result)
                    
                    if success:
                        print(f"    ✅ 성공 ({elapsed_time:.2f}초, 신뢰도: {confidence:.2f})")
                        # 검색된 파일 확인
                        file_names = [s.get("file_name", "") for s in sources[:3]]
                        print(f"    📎 검색된 파일 (상위 3개): {', '.join(file_names)}")
                    else:
                        print(f"    ❌ 실패 ({elapsed_time:.2f}초)")
                    
                except Exception as e:
                    print(f"    ❌ 오류: {e}")
                    results.append({
                        "scenario": scenario['name'],
                        "question": question,
                        "error": str(e),
                        "question_type": "topic_switching"
                    })
        
        return results
    
    def analyze_results(self, pdf_results: List[Dict], pptx_results: List[Dict], 
                       topic_results: List[Dict]) -> Dict[str, Any]:
        """결과 분석"""
        print("\n" + "="*80)
        print("📊 Phase 6: 결과 분석")
        print("="*80)
        
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "pdf_results": {
                "total": len(pdf_results),
                "successful": len([r for r in pdf_results if r.get("success", False)]),
                "failed": len([r for r in pdf_results if "error" in r]),
                "avg_elapsed_time": sum([r.get("elapsed_time", 0) for r in pdf_results]) / len(pdf_results) if pdf_results else 0,
                "avg_confidence": sum([r.get("confidence", 0) for r in pdf_results]) / len(pdf_results) if pdf_results else 0
            },
            "pptx_results": {
                "total": len(pptx_results),
                "successful": len([r for r in pptx_results if r.get("success", False)]),
                "failed": len([r for r in pptx_results if "error" in r]),
                "avg_elapsed_time": sum([r.get("elapsed_time", 0) for r in pptx_results]) / len(pptx_results) if pptx_results else 0,
                "avg_confidence": sum([r.get("confidence", 0) for r in pptx_results]) / len(pptx_results) if pptx_results else 0
            },
            "topic_switching_results": {
                "total": len(topic_results),
                "successful": len([r for r in topic_results if r.get("success", False)]),
                "failed": len([r for r in topic_results if "error" in r]),
                "avg_elapsed_time": sum([r.get("elapsed_time", 0) for r in topic_results]) / len(topic_results) if topic_results else 0,
                "avg_confidence": sum([r.get("confidence", 0) for r in topic_results]) / len(topic_results) if topic_results else 0
            }
        }
        
        # 전체 통계
        all_results = pdf_results + pptx_results + topic_results
        analysis["overall"] = {
            "total": len(all_results),
            "successful": len([r for r in all_results if r.get("success", False)]),
            "failed": len([r for r in all_results if "error" in r]),
            "avg_elapsed_time": sum([r.get("elapsed_time", 0) for r in all_results]) / len(all_results) if all_results else 0,
            "avg_confidence": sum([r.get("confidence", 0) for r in all_results]) / len(all_results) if all_results else 0
        }
        
        # 출력
        print("\n📈 테스트 결과 요약:")
        print(f"\n  PDF 문서:")
        print(f"    - 총 질문: {analysis['pdf_results']['total']}")
        print(f"    - 성공: {analysis['pdf_results']['successful']}")
        print(f"    - 실패: {analysis['pdf_results']['failed']}")
        print(f"    - 평균 응답 시간: {analysis['pdf_results']['avg_elapsed_time']:.2f}초")
        print(f"    - 평균 신뢰도: {analysis['pdf_results']['avg_confidence']:.2f}")
        
        print(f"\n  PPTX 문서:")
        print(f"    - 총 질문: {analysis['pptx_results']['total']}")
        print(f"    - 성공: {analysis['pptx_results']['successful']}")
        print(f"    - 실패: {analysis['pptx_results']['failed']}")
        print(f"    - 평균 응답 시간: {analysis['pptx_results']['avg_elapsed_time']:.2f}초")
        print(f"    - 평균 신뢰도: {analysis['pptx_results']['avg_confidence']:.2f}")
        
        print(f"\n  주제 변경 테스트:")
        print(f"    - 총 질문: {analysis['topic_switching_results']['total']}")
        print(f"    - 성공: {analysis['topic_switching_results']['successful']}")
        print(f"    - 실패: {analysis['topic_switching_results']['failed']}")
        print(f"    - 평균 응답 시간: {analysis['topic_switching_results']['avg_elapsed_time']:.2f}초")
        print(f"    - 평균 신뢰도: {analysis['topic_switching_results']['avg_confidence']:.2f}")
        
        print(f"\n  전체:")
        print(f"    - 총 질문: {analysis['overall']['total']}")
        print(f"    - 성공: {analysis['overall']['successful']}")
        print(f"    - 실패: {analysis['overall']['failed']}")
        print(f"    - 평균 응답 시간: {analysis['overall']['avg_elapsed_time']:.2f}초")
        print(f"    - 평균 신뢰도: {analysis['overall']['avg_confidence']:.2f}")
        
        return analysis
    
    def save_results(self, pdf_results: List[Dict], pptx_results: List[Dict], 
                    topic_results: List[Dict], analysis: Dict[str, Any]) -> str:
        """결과 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"test_results_{timestamp}.json"
        
        results_data = {
            "analysis": analysis,
            "pdf_results": pdf_results,
            "pptx_results": pptx_results,
            "topic_switching_results": topic_results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 결과 저장 완료: {output_file}")
        return str(output_file)
    
    def run_all_tests(self, clear_existing: bool = True) -> str:
        """전체 테스트 실행"""
        self.test_start_time = time.perf_counter()
        
        print("\n" + "="*80)
        print("[RAG] 성능 테스트 시작")
        print("="*80)
        
        # Phase 1: 환경 준비
        if not self.setup_test_environment(clear_existing):
            return None
        
        # Phase 2: 문서 임베딩
        if not self.embed_test_documents():
            return None
        
        # Reference 결과 로드
        pdf_ref, pptx_ref = self.load_reference_results()
        
        # Phase 3: PDF 테스트
        pdf_results = []
        if pdf_ref:
            pdf_results = self.test_pdf_documents(pdf_ref)
        else:
            print("\n⚠️  PDF Reference 결과가 없어 PDF 테스트를 건너뜁니다.")
        
        # Phase 4: PPTX 테스트
        pptx_results = []
        if pptx_ref:
            pptx_results = self.test_pptx_documents(pptx_ref)
        else:
            print("\n⚠️  PPTX Reference 결과가 없어 PPTX 테스트를 건너뜁니다.")
        
        # Phase 5: 주제 변경 테스트
        topic_results = self.test_topic_switching()
        
        # Phase 6: 결과 분석
        analysis = self.analyze_results(pdf_results, pptx_results, topic_results)
        
        # Phase 7: 결과 저장
        output_file = self.save_results(pdf_results, pptx_results, topic_results, analysis)
        
        total_time = time.perf_counter() - self.test_start_time
        print(f"\n✅ 전체 테스트 완료 (총 소요 시간: {total_time:.2f}초)")
        
        return output_file


if __name__ == "__main__":
    tester = RAGPerformanceTester()
    output_file = tester.run_all_tests(clear_existing=True)
    
    if output_file:
        print(f"\n📄 결과 파일: {output_file}")
    else:
        print("\n❌ 테스트 실패")

