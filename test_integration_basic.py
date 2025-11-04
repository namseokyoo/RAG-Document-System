"""
Phase 1.3: 핵심 기능 통합 테스트 (시나리오 A, B)
실제 RAG 파이프라인 End-to-End 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
import tempfile
import shutil
from typing import List

from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from utils.rag_chain import RAGChain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document


class IntegrationTest:
    """통합 테스트 클래스"""

    def __init__(self):
        self.temp_dir = None
        self.test_results = []
        self.vector_manager = None
        self.rag_chain = None

    def setup(self):
        """테스트 환경 설정"""
        print("\n[SETUP] 테스트 환경 초기화 중...")

        # 임시 디렉토리 생성
        self.temp_dir = tempfile.mkdtemp(prefix="rag_test_")
        print(f"  - 임시 디렉토리: {self.temp_dir}")

        # 문서 프로세서 생성 (Text Splitter)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )
        print("  - 텍스트 스플리터 생성 완료")

        # 벡터 스토어 생성 (임시 디렉토리 사용)
        self.vector_manager = VectorStoreManager(
            persist_directory=os.path.join(self.temp_dir, "chroma_db"),
            embedding_api_type="ollama",
            embedding_base_url="http://localhost:11434",
            embedding_model="mxbai-embed-large",  # 사용 가능한 모델로 변경
            embedding_api_key=""
        )
        print("  - 벡터 스토어 매니저 생성 완료")

        # RAG Chain 생성
        vectorstore_obj = self.vector_manager  # VectorStoreManager 객체 전달
        self.rag_chain = RAGChain(
            vectorstore=vectorstore_obj,
            llm_api_type="ollama",
            llm_base_url="http://localhost:11434",
            llm_model="gemma3:4b",
            temperature=0.7,
            top_k=3,
            use_reranker=True,
            reranker_model="multilingual-mini",
            reranker_initial_k=20,
            enable_synonym_expansion=True,
            enable_multi_query=True,
            multi_query_num=3
        )
        print("  - RAG Chain 생성 완료")

        return True

    def teardown(self):
        """테스트 환경 정리"""
        print("\n[TEARDOWN] 테스트 환경 정리 중...")
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"  - 임시 디렉토리 삭제: {self.temp_dir}")
            except Exception as e:
                print(f"  - 임시 디렉토리 삭제 실패: {e}")

    def log(self, test_name: str, passed: bool, message: str = ""):
        """테스트 결과 로깅"""
        status = "[PASS]" if passed else "[FAIL]"
        result = f"{status} - {test_name}"
        if message:
            result += f": {message}"
        print(result)
        self.test_results.append((test_name, passed, message))

    def create_sample_documents(self) -> List[Path]:
        """샘플 텍스트 문서 생성"""
        print("\n[샘플 문서 생성]")

        docs_dir = Path(self.temp_dir) / "test_docs"
        docs_dir.mkdir(exist_ok=True)

        # OLED 관련 문서
        doc1_content = """
        OLED (Organic Light-Emitting Diode) Technology Overview

        OLEDs are solid-state devices composed of thin films of organic molecules that
        create light with the application of electricity. OLEDs can provide brighter,
        crisper displays on electronic devices and use less power than conventional
        light-emitting diodes (LEDs) or liquid crystal displays (LCDs).

        Key advantages of OLED technology:
        1. High efficiency: OLEDs can achieve up to 30% external quantum efficiency
        2. Flexibility: Can be fabricated on flexible substrates
        3. Wide viewing angles: Nearly 180 degrees
        4. Fast response time: Less than 1 microsecond

        The TADF (Thermally Activated Delayed Fluorescence) mechanism has been shown
        to achieve high efficiency by harvesting triplet excitons.
        """

        doc2_content = """
        TADF Materials for OLED Applications

        TADF (Thermally Activated Delayed Fluorescence) emitters are a class of
        organic materials that can achieve 100% internal quantum efficiency by
        up-converting non-emissive triplet excitons to emissive singlet excitons.

        Recent developments:
        - ACRSA-based TADF materials show improved efficiency
        - DABNA derivatives demonstrate narrow emission spectra
        - Multi-resonance TADF (MR-TADF) achieves high color purity

        Performance metrics:
        - External quantum efficiency (EQE): 25-35%
        - Photoluminescence quantum yield (PLQY): >90%
        - Device lifetime: >10,000 hours at 1000 cd/m²
        """

        doc3_content = """
        Business Strategy and Market Analysis

        The global OLED market is experiencing significant growth, driven by
        increasing demand for smartphones and televisions. Companies are investing
        heavily in R&D to improve manufacturing efficiency and reduce costs.

        Market projections:
        - Market size: $35 billion by 2025
        - Annual growth rate: 12-15%
        - Key players: Samsung, LG, Sony

        Strategic considerations:
        - Supply chain optimization
        - Patent portfolio management
        - Competitive positioning
        """

        # 문서 저장
        docs = []
        for idx, content in enumerate([doc1_content, doc2_content, doc3_content], 1):
            doc_path = docs_dir / f"test_doc_{idx}.txt"
            doc_path.write_text(content, encoding='utf-8')
            docs.append(doc_path)
            print(f"  - 생성: {doc_path.name} ({len(content)} chars)")

        return docs

    def test_scenario_a_document_indexing(self):
        """시나리오 A: 문서 업로드 및 인덱싱"""
        print("\n" + "=" * 80)
        print("시나리오 A: 문서 업로드 및 인덱싱")
        print("=" * 80)

        try:
            # 1. 샘플 문서 생성
            print("\n[1단계] 샘플 문서 생성")
            docs = self.create_sample_documents()
            self.log("샘플 문서 생성", len(docs) == 3, f"{len(docs)}개 문서")

            # 2. 문서 처리 (청킹)
            print("\n[2단계] 문서 청킹")
            all_chunks = []
            for doc_path in docs:
                with open(doc_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Document 객체 생성
                doc = Document(
                    page_content=content,
                    metadata={"source": doc_path.name}
                )

                # 텍스트 분할
                chunks = self.text_splitter.split_documents([doc])
                all_chunks.extend(chunks)
                print(f"  - {doc_path.name}: {len(chunks)}개 청크")

            chunk_count = len(all_chunks)
            self.log("문서 청킹", chunk_count > 0, f"{chunk_count}개 청크 생성")

            # 3. 벡터 스토어에 저장
            print("\n[3단계] 벡터 임베딩 및 저장")
            print("  [INFO] Ollama 서버가 실행 중이어야 합니다...")

            try:
                self.vector_manager.add_documents(all_chunks)
                self.log("벡터 임베딩 및 저장", True, "완료")
            except Exception as e:
                error_msg = str(e)
                if "Connection" in error_msg or "Failed to connect" in error_msg:
                    self.log("벡터 임베딩 및 저장", False, "Ollama 서버 연결 실패")
                    print("  [ERROR] Ollama 서버가 실행되고 있지 않습니다.")
                    print("  [INFO] 테스트를 계속하려면 다음 명령으로 Ollama를 시작하세요:")
                    print("         ollama serve")
                    return False
                else:
                    raise

            # 4. 저장 확인
            print("\n[4단계] 저장 확인")
            collection = self.vector_manager.vectorstore._collection
            stored_count = collection.count()
            self.log("저장 확인", stored_count == chunk_count,
                    f"{stored_count}개 문서 저장됨")

            return True

        except Exception as e:
            print(f"\n[ERROR] 시나리오 A 실행 중 오류: {e}")
            import traceback
            traceback.print_exc()
            self.log("시나리오 A", False, str(e))
            return False

    def test_scenario_b_basic_search(self):
        """시나리오 B: 기본 검색"""
        print("\n" + "=" * 80)
        print("시나리오 B: 기본 검색")
        print("=" * 80)

        try:
            # 1. 벡터 검색
            print("\n[1단계] 벡터 검색 (OLED efficiency)")
            query = "OLED efficiency and performance"
            vectorstore = self.vector_manager.get_vectorstore()

            results = vectorstore.similarity_search_with_score(query, k=5)
            self.log("벡터 검색", len(results) > 0,
                    f"{len(results)}개 결과")

            for idx, (doc, score) in enumerate(results[:3], 1):
                print(f"  [{idx}] Score: {score:.3f}")
                print(f"      Content: {doc.page_content[:100]}...")

            # 2. Re-ranker 적용
            print("\n[2단계] Re-ranker 적용")
            if self.rag_chain.use_reranker:
                try:
                    reranked = self.rag_chain.rerank_documents(query, results)
                    self.log("Re-ranker 적용", len(reranked) > 0,
                            f"{len(reranked)}개 결과")

                    print("  Re-ranking 결과:")
                    for idx, (doc, score) in enumerate(reranked[:3], 1):
                        print(f"  [{idx}] Score: {score:.3f}")
                        print(f"      Content: {doc.page_content[:100]}...")
                except Exception as e:
                    self.log("Re-ranker 적용", False, f"Re-ranker 오류: {e}")
                    reranked = results
            else:
                reranked = results
                self.log("Re-ranker 적용", False, "Re-ranker 비활성화")

            # 3. Smart Filtering 적용
            print("\n[3단계] Smart Filtering 적용")
            filtered = self.rag_chain._statistical_outlier_removal(
                reranked, method='mad'
            )
            self.log("Statistical Outlier Removal",
                    len(filtered) > 0, f"{len(filtered)}개 결과")

            filtered = self.rag_chain._reranker_gap_based_cutoff(
                filtered, min_docs=2
            )
            self.log("Gap-based Cutoff",
                    len(filtered) > 0, f"{len(filtered)}개 결과")

            # 4. 최종 결과
            print("\n[최종 결과]")
            for idx, (doc, score) in enumerate(filtered[:3], 1):
                source = doc.metadata.get('source', 'Unknown')
                print(f"  [{idx}] Score: {score:.3f}, Source: {source}")
                print(f"      {doc.page_content[:150]}...")

            return True

        except Exception as e:
            print(f"\n[ERROR] 시나리오 B 실행 중 오류: {e}")
            import traceback
            traceback.print_exc()
            self.log("시나리오 B", False, str(e))
            return False

    def run_all_tests(self):
        """모든 테스트 실행"""
        print("=" * 80)
        print("Phase 1.3: 핵심 기능 통합 테스트 시작")
        print("=" * 80)

        try:
            # 환경 설정
            if not self.setup():
                print("[ERROR] 테스트 환경 설정 실패")
                return False

            # 시나리오 A 실행
            scenario_a_passed = self.test_scenario_a_document_indexing()

            # 시나리오 B 실행 (시나리오 A가 성공한 경우만)
            if scenario_a_passed:
                scenario_b_passed = self.test_scenario_b_basic_search()
            else:
                print("\n[SKIP] 시나리오 A 실패로 시나리오 B 건너뜀")
                scenario_b_passed = False

            # 결과 요약
            self.print_summary()

        finally:
            # 환경 정리
            self.teardown()

    def print_summary(self):
        """테스트 결과 요약"""
        print("\n" + "=" * 80)
        print("테스트 결과 요약")
        print("=" * 80)

        passed = sum(1 for _, result, _ in self.test_results if result)
        total = len(self.test_results)

        for test_name, result, message in self.test_results:
            status = "[OK]" if result else "[NG]"
            print(f"{status} {test_name}")
            if message and not result:
                print(f"   -> {message}")

        print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")

        if passed == total:
            print("\n[SUCCESS] 모든 통합 테스트 통과!")
            return True
        else:
            print(f"\n[PARTIAL] {total - passed}개 테스트 실패")
            return False


def main():
    """메인 함수"""
    tester = IntegrationTest()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
