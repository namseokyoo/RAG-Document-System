"""
네트워크 드라이브 스캔 유틸리티
- Windows 환경에서 A~Z 드라이브를 스캔하여 특정 볼륨 레이블을 가진 드라이브 찾기
- 공유 DB 경로 자동 탐색
"""

import os
import string
from typing import Optional, Tuple
import ctypes
from ctypes import windll


class DriveScanner:
    """Windows 드라이브 스캔 및 공유 DB 경로 탐색"""

    # 공유 DB 설정
    TARGET_VOLUME_LABEL = "LGDKRB.OC 연구_개발5팀"
    SHARED_DB_RELATIVE_PATH = r"OC_RAG_system_DB\data\chroma_db"

    @staticmethod
    def get_volume_label(drive_letter: str) -> Optional[str]:
        """
        드라이브의 볼륨 레이블을 가져옴

        Args:
            drive_letter: 드라이브 문자 (예: 'C', 'D', 'U')

        Returns:
            볼륨 레이블 문자열 또는 None
        """
        try:
            drive_path = f"{drive_letter}:\\"

            # 드라이브가 존재하는지 확인
            if not os.path.exists(drive_path):
                return None

            # Windows API를 사용하여 볼륨 레이블 가져오기
            volume_name_buffer = ctypes.create_unicode_buffer(1024)
            file_system_name_buffer = ctypes.create_unicode_buffer(1024)
            serial_number = None
            max_component_length = None
            file_system_flags = None

            result = windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive_path),
                volume_name_buffer,
                ctypes.sizeof(volume_name_buffer),
                serial_number,
                max_component_length,
                file_system_flags,
                file_system_name_buffer,
                ctypes.sizeof(file_system_name_buffer)
            )

            if result:
                return volume_name_buffer.value
            else:
                return None

        except Exception as e:
            # 조용히 실패 (접근 불가능한 드라이브일 수 있음)
            return None

    @staticmethod
    def scan_all_drives() -> dict:
        """
        모든 드라이브를 스캔하여 볼륨 레이블 정보 수집

        Returns:
            {드라이브_문자: 볼륨_레이블} 딕셔너리
        """
        drive_info = {}

        # A~Z까지 모든 드라이브 문자 스캔
        for letter in string.ascii_uppercase:
            label = DriveScanner.get_volume_label(letter)
            if label:
                drive_info[letter] = label
                print(f"[DriveScanner] {letter}: - {label}")

        return drive_info

    @staticmethod
    def find_shared_db_drive() -> Optional[Tuple[str, str]]:
        """
        공유 DB가 있는 드라이브를 찾음

        Returns:
            (드라이브_문자, DB_전체_경로) 튜플 또는 None
        """
        print(f"[DriveScanner] 공유 DB 검색 시작...")
        print(f"[DriveScanner] 대상 볼륨 레이블: '{DriveScanner.TARGET_VOLUME_LABEL}'")

        # 모든 드라이브 스캔
        for letter in string.ascii_uppercase:
            try:
                # 볼륨 레이블 확인
                label = DriveScanner.get_volume_label(letter)

                if label and label == DriveScanner.TARGET_VOLUME_LABEL:
                    print(f"[DriveScanner] ✓ 대상 드라이브 발견: {letter}:")

                    # DB 경로 확인
                    db_path = os.path.join(f"{letter}:\\", DriveScanner.SHARED_DB_RELATIVE_PATH)

                    # 경로가 존재하는지 확인
                    if os.path.exists(db_path):
                        print(f"[DriveScanner] ✓ 공유 DB 경로 확인: {db_path}")
                        return (letter, db_path)
                    else:
                        print(f"[DriveScanner] ✗ DB 경로가 존재하지 않음: {db_path}")
                        print(f"[DriveScanner]   경로를 생성하시겠습니까? (수동 생성 필요)")
                        # 경로를 자동으로 생성할 수도 있지만, 안전을 위해 수동 생성 권장

            except Exception as e:
                # 조용히 실패 (접근 권한 없는 드라이브 등)
                continue

        print(f"[DriveScanner] ✗ 공유 DB를 찾지 못했습니다.")
        return None

    @staticmethod
    def verify_db_path(db_path: str) -> bool:
        """
        DB 경로가 유효한지 확인

        Args:
            db_path: 확인할 DB 경로

        Returns:
            경로가 유효하면 True
        """
        try:
            # 경로가 존재하는지 확인
            if not os.path.exists(db_path):
                return False

            # 읽기/쓰기 권한 확인
            test_file = os.path.join(db_path, ".test_write_permission")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                return True
            except Exception:
                print(f"[DriveScanner] 경고: {db_path}에 쓰기 권한이 없습니다.")
                return False

        except Exception as e:
            print(f"[DriveScanner] DB 경로 검증 실패: {e}")
            return False

    @staticmethod
    def create_shared_db_path(drive_letter: str) -> Optional[str]:
        """
        공유 DB 경로를 생성

        Args:
            drive_letter: 드라이브 문자

        Returns:
            생성된 경로 또는 None
        """
        try:
            db_path = os.path.join(f"{drive_letter}:\\", DriveScanner.SHARED_DB_RELATIVE_PATH)
            os.makedirs(db_path, exist_ok=True)
            print(f"[DriveScanner] 공유 DB 경로 생성 완료: {db_path}")
            return db_path
        except Exception as e:
            print(f"[DriveScanner] 공유 DB 경로 생성 실패: {e}")
            return None


def test_drive_scanner():
    """드라이브 스캐너 테스트"""
    print("=" * 50)
    print("드라이브 스캔 테스트")
    print("=" * 50)

    # 모든 드라이브 스캔
    drives = DriveScanner.scan_all_drives()
    print(f"\n발견된 드라이브: {len(drives)}개")

    # 공유 DB 찾기
    print("\n" + "=" * 50)
    result = DriveScanner.find_shared_db_drive()

    if result:
        drive_letter, db_path = result
        print(f"\n✓ 공유 DB 발견!")
        print(f"  드라이브: {drive_letter}:")
        print(f"  경로: {db_path}")

        # 경로 검증
        if DriveScanner.verify_db_path(db_path):
            print(f"  상태: 정상 (읽기/쓰기 가능)")
        else:
            print(f"  상태: 경고 (권한 문제)")
    else:
        print(f"\n✗ 공유 DB를 찾을 수 없습니다.")
        print(f"  - 네트워크 드라이브가 연결되어 있는지 확인하세요.")
        print(f"  - 볼륨 레이블: '{DriveScanner.TARGET_VOLUME_LABEL}'")


if __name__ == "__main__":
    test_drive_scanner()
