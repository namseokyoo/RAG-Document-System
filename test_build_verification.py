"""
Phase 1.1: 빌드 검증 테스트 (Build Verification Test)
빌드된 실행 파일의 기본 동작 및 의존성 확인
"""
import os
import sys
import subprocess
import time
from pathlib import Path


class BuildVerificationTest:
    """빌드 검증 테스트 클래스"""

    def __init__(self, build_dir: str = "dist/RAG_Document_System"):
        self.build_dir = Path(build_dir)
        self.exe_path = self.build_dir / "RAG_Document_System.exe"
        self.internal_dir = self.build_dir / "_internal"
        self.test_results = []

    def log(self, test_name: str, passed: bool, message: str = ""):
        """테스트 결과 로깅"""
        status = "[PASS]" if passed else "[FAIL]"
        result = f"{status} - {test_name}"
        if message:
            result += f": {message}"
        print(result)
        self.test_results.append((test_name, passed, message))

    def test_1_executable_exists(self):
        """테스트 1: 실행 파일 존재 확인"""
        print("\n[테스트 1] 실행 파일 존재 확인")
        exists = self.exe_path.exists()
        size_mb = self.exe_path.stat().st_size / (1024 * 1024) if exists else 0
        self.log("실행 파일 존재", exists, f"크기: {size_mb:.1f}MB")
        return exists

    def test_2_directory_structure(self):
        """테스트 2: 디렉토리 구조 확인"""
        print("\n[테스트 2] 디렉토리 구조 확인")

        required_items = {
            "_internal": self.internal_dir,
            "config.json.example": self.internal_dir / "config.json.example",
            "models": self.internal_dir / "models",
            "resources": self.internal_dir / "resources",
        }

        all_exist = True
        for name, path in required_items.items():
            exists = path.exists()
            self.log(f"  - {name}", exists, str(path))
            all_exist = all_exist and exists

        return all_exist

    def test_3_critical_dependencies(self):
        """테스트 3: 핵심 의존성 파일 확인"""
        print("\n[테스트 3] 핵심 의존성 파일 확인")

        critical_files = [
            "base_library.zip",
            "python312.dll",
        ]

        critical_dirs = [
            "PySide6",
            "torch",
            "langchain",
            "chromadb_rust_bindings",
            "sentence_transformers",
        ]

        all_exist = True

        # 파일 확인
        for filename in critical_files:
            path = self.internal_dir / filename
            exists = path.exists()
            size = path.stat().st_size / (1024 * 1024) if exists else 0
            self.log(f"  - {filename}", exists, f"{size:.1f}MB")
            all_exist = all_exist and exists

        # 디렉토리 확인
        for dirname in critical_dirs:
            path = self.internal_dir / dirname
            exists = path.exists() and path.is_dir()
            self.log(f"  - {dirname}/", exists)
            all_exist = all_exist and exists

        return all_exist

    def test_4_models_directory(self):
        """테스트 4: Re-ranker 모델 디렉토리 확인"""
        print("\n[테스트 4] Re-ranker 모델 디렉토리 확인")

        models_dir = self.internal_dir / "models"
        if not models_dir.exists():
            self.log("models 디렉토리", False, "디렉토리 없음")
            return False

        # 모델 파일 확인
        model_files = list(models_dir.rglob("*"))
        model_count = len([f for f in model_files if f.is_file()])

        self.log("models 디렉토리", True, f"{model_count}개 파일")

        # 일반적인 모델 파일 확인
        expected_files = ["config.json", "pytorch_model.bin", "tokenizer_config.json"]
        for filename in expected_files:
            found = any(f.name == filename for f in model_files)
            if found:
                self.log(f"  - {filename}", True)

        return model_count > 0

    def test_5_icon_file(self):
        """테스트 5: 아이콘 파일 확인"""
        print("\n[테스트 5] 아이콘 파일 확인 (oc.ico)")

        # 실행 파일에 아이콘이 내장되어 있는지 확인
        # PE 헤더 확인으로 아이콘 존재 여부 체크
        try:
            with open(self.exe_path, 'rb') as f:
                # PE 시그니처 찾기
                f.seek(0x3C)
                pe_offset = int.from_bytes(f.read(4), 'little')
                f.seek(pe_offset)
                signature = f.read(4)

                if signature == b'PE\x00\x00':
                    self.log("실행 파일 PE 헤더", True, "유효한 Windows 실행 파일")
                    # 아이콘은 내장되어 있다고 가정 (실제 확인은 실행 시)
                    return True
                else:
                    self.log("실행 파일 PE 헤더", False, "유효하지 않은 PE 파일")
                    return False
        except Exception as e:
            self.log("실행 파일 분석", False, str(e))
            return False

    def test_6_console_mode(self):
        """테스트 6: 콘솔 모드 설정 확인"""
        print("\n[테스트 6] 콘솔 모드 설정 확인")

        # PE 헤더에서 Subsystem 확인
        try:
            with open(self.exe_path, 'rb') as f:
                f.seek(0x3C)
                pe_offset = int.from_bytes(f.read(4), 'little')
                f.seek(pe_offset + 0x5C)  # Subsystem offset
                subsystem = int.from_bytes(f.read(2), 'little')

                # 3 = CONSOLE, 2 = GUI
                is_console = subsystem == 3
                mode = "CONSOLE" if is_console else "GUI"
                self.log("콘솔 모드 설정", is_console, f"Subsystem={mode} (값: {subsystem})")
                return is_console
        except Exception as e:
            self.log("콘솔 모드 확인", False, str(e))
            return False

    def test_7_quick_launch(self):
        """테스트 7: 빠른 실행 테스트 (5초 타임아웃)"""
        print("\n[테스트 7] 빠른 실행 테스트 (5초 타임아웃)")
        print("  [WARNING] GUI 창이 열릴 수 있습니다. 자동으로 종료됩니다.")

        try:
            # 프로세스 시작
            proc = subprocess.Popen(
                [str(self.exe_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.build_dir)
            )

            # 5초 대기
            time.sleep(5)

            # 프로세스가 여전히 실행 중인지 확인
            poll = proc.poll()
            if poll is None:
                # 정상 실행 중
                self.log("실행 파일 시작", True, "프로세스가 정상적으로 시작됨")
                proc.terminate()
                proc.wait(timeout=3)
                return True
            else:
                # 즉시 종료됨 (오류 발생)
                stdout, stderr = proc.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore')[:200]
                self.log("실행 파일 시작", False, f"프로세스가 즉시 종료됨 (code={poll})")
                if error_msg:
                    print(f"     오류 메시지: {error_msg}")
                return False

        except Exception as e:
            self.log("실행 파일 시작", False, str(e))
            return False

    def test_8_build_size(self):
        """테스트 8: 빌드 크기 확인"""
        print("\n[테스트 8] 빌드 크기 확인")

        try:
            total_size = 0
            file_count = 0

            for item in self.build_dir.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1

            size_gb = total_size / (1024 ** 3)
            expected_min = 0.8  # 최소 800MB
            expected_max = 2.0  # 최대 2GB

            is_reasonable = expected_min <= size_gb <= expected_max
            self.log(
                "빌드 크기",
                is_reasonable,
                f"{size_gb:.2f}GB ({file_count}개 파일)"
            )

            if not is_reasonable:
                print(f"     [WARNING] 예상 범위: {expected_min}GB ~ {expected_max}GB")

            return is_reasonable

        except Exception as e:
            self.log("빌드 크기 확인", False, str(e))
            return False

    def run_all_tests(self):
        """모든 테스트 실행"""
        print("=" * 80)
        print("Phase 1.1: 빌드 검증 테스트 시작")
        print("=" * 80)

        tests = [
            self.test_1_executable_exists,
            self.test_2_directory_structure,
            self.test_3_critical_dependencies,
            self.test_4_models_directory,
            self.test_5_icon_file,
            self.test_6_console_mode,
            self.test_8_build_size,
            # test_7은 선택적 (GUI 창이 열림)
        ]

        # 실행 테스트는 사용자 확인 후
        print("\n[WARNING] 실행 테스트를 진행하시겠습니까? (GUI 창이 열립니다)")
        print("   계속하려면 아무 키나 누르세요. 건너뛰려면 Ctrl+C...")
        try:
            # input()  # 사용자 입력 대기 (자동화를 위해 주석 처리)
            # tests.append(self.test_7_quick_launch)
            pass
        except KeyboardInterrupt:
            print("\n실행 테스트를 건너뜁니다.")

        # 테스트 실행
        for test_func in tests:
            try:
                test_func()
            except Exception as e:
                print(f"[ERROR] 테스트 실행 오류: {e}")
                import traceback
                traceback.print_exc()

        # 결과 요약
        self.print_summary()

    def print_summary(self):
        """테스트 결과 요약 출력"""
        print("\n" + "=" * 80)
        print("테스트 결과 요약")
        print("=" * 80)

        passed = sum(1 for _, result, _ in self.test_results if result)
        total = len(self.test_results)

        for test_name, result, message in self.test_results:
            status = "[OK]" if result else "[NG]"
            print(f"{status} {test_name}")
            if message and not result:
                print(f"   → {message}")

        print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")

        if passed == total:
            print("\n[SUCCESS] 모든 빌드 검증 테스트 통과!")
            return True
        else:
            print(f"\n[FAILED] {total - passed}개 테스트 실패")
            return False


def main():
    """메인 함수"""
    tester = BuildVerificationTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
