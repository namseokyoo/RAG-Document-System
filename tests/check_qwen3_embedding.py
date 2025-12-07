#!/usr/bin/env python3
"""
qwen3-embedding-8B 모델 특성 확인 스크립트
사내 환경에서 실행하여 차원, 정규화, 속도 확인
"""

import time
import numpy as np
import requests
import json
import os


def load_config():
    """config.json에서 임베딩 설정 로드"""
    config_path = "config.json"

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"[INFO] config.json 로드 성공")
                return config
        except Exception as e:
            print(f"[WARN] config.json 로드 실패: {e}")

    # 기본값 반환
    return {
        "embedding_base_url": "http://localhost:11434",
        "embedding_api_type": None,  # 자동 감지
        "embedding_api_key": ""
    }


def get_embedding_via_request(
    base_url: str,
    model: str,
    text: str,
    api_type: str = None,
    api_key: str = "",
    timeout: int = 60
) -> list:
    """
    Request로 임베딩 API 호출 (utils/request_embeddings.py 방식)
    Ollama 및 OpenAI 호환 API 모두 지원

    Args:
        base_url: API 서버 URL
        model: 모델 이름
        text: 임베딩할 텍스트
        api_type: API 타입 ("ollama" 또는 "openai", None이면 자동 감지)
        api_key: API 키 (OpenAI 호환 API용)
        timeout: 요청 타임아웃 (초)

    Returns:
        임베딩 벡터 (list of float)
    """
    # API 타입 자동 감지 (utils/request_embeddings.py 방식)
    if api_type is None:
        if "ollama" in base_url or ":11434" in base_url:
            api_type = "ollama"
        else:
            api_type = "openai"

    # 엔드포인트 및 페이로드 설정
    if api_type == "ollama":
        endpoint = f"{base_url}/api/embeddings"
        payload = {
            "model": model,
            "prompt": text  # Ollama는 'prompt' 사용
        }
    else:
        endpoint = f"{base_url}/v1/embeddings"
        payload = {
            "model": model,
            "input": text  # OpenAI는 'input' 사용
        }

    # 헤더 설정
    headers = {"Content-Type": "application/json"}
    if api_key and api_type != "ollama":
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        print(f"[DEBUG] API 타입: {api_type}")
        print(f"[DEBUG] 요청 URL: {endpoint}")
        print(f"[DEBUG] 요청 모델: {model}")
        print(f"[DEBUG] 텍스트 길이: {len(text)}자")

        response = requests.post(
            endpoint,
            json=payload,
            timeout=timeout,
            headers=headers
        )

        print(f"[DEBUG] 응답 상태: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            # 응답 파싱 (API 타입별)
            if api_type == "ollama":
                embedding = result.get("embedding", [])
            else:
                # OpenAI 호환 API
                embedding = result.get("data", [{}])[0].get("embedding", [])

            print(f"[DEBUG] 임베딩 성공: {len(embedding)}차원")
            return embedding
        else:
            error_msg = f"API 오류: {response.status_code} - {response.text}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)

    except requests.exceptions.RequestException as e:
        error_msg = f"네트워크 오류: {e}"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"임베딩 처리 오류: {e}"
        print(f"[ERROR] {error_msg}")
        raise Exception(error_msg)


def check_qwen3_properties():
    """qwen3-embedding-8B 모델 특성 확인"""

    print("=" * 60)
    print("qwen3-embedding-8B 모델 특성 확인")
    print("=" * 60)

    # config.json에서 설정 로드
    config = load_config()

    base_url = config.get("embedding_base_url", "http://localhost:11434").rstrip('/')
    api_type = config.get("embedding_api_type")  # None이면 자동 감지
    api_key = config.get("embedding_api_key", "")
    model_name = "qwen3-embedding-8B"

    print(f"\n[설정 정보]")
    print(f"  - Base URL: {base_url}")
    print(f"  - API Type: {api_type if api_type else '자동 감지'}")
    print(f"  - Model: {model_name}")
    print(f"  - API Key: {'설정됨' if api_key else '없음'}")

    # 1. API 연결 테스트 및 모델 확인
    print("\n[1/5] API 연결 및 모델 확인...")

    # API 타입 결정 (자동 감지)
    detected_api_type = api_type
    if detected_api_type is None:
        if "ollama" in base_url or ":11434" in base_url:
            detected_api_type = "ollama"
        else:
            detected_api_type = "openai"

    print(f"[DEBUG] 감지된 API 타입: {detected_api_type}")

    try:
        if detected_api_type == "ollama":
            # Ollama 서비스 상태 확인
            health_url = f"{base_url}/api/tags"
            print(f"[DEBUG] 연결 테스트 URL: {health_url}")

            response = requests.get(health_url, timeout=10)
            print(f"[DEBUG] 연결 응답 상태: {response.status_code}")

            if response.status_code == 200:
                print(f"  ✓ Ollama 서버 연결 성공")

                # 사용 가능한 모델 확인
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]

                print(f"  ✓ 사용 가능한 모델 수: {len(model_names)}")

                if model_name in model_names:
                    print(f"  ✓ '{model_name}' 모델 확인됨")
                else:
                    print(f"  ⚠ '{model_name}' 모델이 로드되지 않았습니다")
                    print(f"  ℹ 사용 가능한 모델: {model_names[:5]}")  # 처음 5개만 표시
                    print(f"  ℹ 해결 방법: ollama pull {model_name}")
                    # 모델이 없어도 계속 진행 (테스트 목적)
            else:
                print(f"  ✗ Ollama 서비스 응답 오류: {response.status_code}")
                return
        else:
            # OpenAI 호환 API: 간단한 연결 테스트 (임베딩 직접 시도)
            print(f"  ℹ OpenAI 호환 API 모드 - 모델 목록 확인 스킵")
            print(f"  ℹ 다음 단계에서 임베딩 테스트로 연결 확인 진행")

    except Exception as e:
        print(f"  ✗ 연결 실패: {e}")
        print(f"  ✗ API 서버가 {base_url}에서 실행 중인지 확인하세요")
        return

    # 2. 임베딩 차원 확인
    print("\n[2/5] 임베딩 차원 확인...")
    test_text = "OLED 디바이스의 효율 향상"

    try:
        start = time.time()
        embedding = get_embedding_via_request(
            base_url, model_name, test_text,
            api_type=api_type, api_key=api_key
        )
        elapsed = time.time() - start

        dimension = len(embedding)
        print(f"  ✓ 임베딩 차원: {dimension}")
        print(f"  ✓ 단일 쿼리 임베딩 시간: {elapsed:.3f}초")
    except Exception as e:
        print(f"  ✗ 임베딩 생성 실패: {e}")
        return

    # 3. 정규화 여부 확인
    print("\n[3/5] 벡터 정규화 여부 확인...")
    norm = np.linalg.norm(embedding)
    is_normalized = abs(norm - 1.0) < 0.01

    print(f"  ✓ L2 Norm: {norm:.6f}")
    if is_normalized:
        print(f"  ✓ 정규화됨 → cosine/ip 거리 함수 권장")
    else:
        print(f"  ✓ 정규화 안됨 → l2 거리 함수 유지")

    # 4. 배치 임베딩 속도 확인
    print("\n[4/5] 배치 임베딩 속도 확인...")
    test_texts = [
        "백금 촉매의 특성 연구",
        "양자점 합성 공정 최적화",
        "페로브스카이트 태양전지 효율",
        "유기 발광 다이오드 수명 향상",
        "그래핀 기반 센서 개발"
    ]

    start = time.time()
    batch_embeddings = []

    try:
        for i, text in enumerate(test_texts, 1):
            print(f"  [{i}/5] 임베딩 중...")
            emb = get_embedding_via_request(
                base_url, model_name, text,
                api_type=api_type, api_key=api_key, timeout=60
            )
            batch_embeddings.append(emb)

        elapsed = time.time() - start
        print(f"  ✓ 5개 문서 임베딩 시간: {elapsed:.3f}초")
        print(f"  ✓ 평균 속도: {elapsed/5:.3f}초/문서")

    except Exception as e:
        print(f"  ✗ 배치 임베딩 실패: {e}")
        elapsed = time.time() - start
        print(f"  ℹ {len(batch_embeddings)}/5개 성공 후 실패")
        if len(batch_embeddings) == 0:
            print("  ✗ 임베딩을 하나도 생성하지 못했습니다. 모델 상태를 확인하세요.")
            return

    # 5. 기존 모델과 비교
    print("\n[5/5] mxbai-embed-large와 비교...")

    # elapsed 값 확인 (배치 임베딩이 성공했을 때만 사용)
    if len(batch_embeddings) > 0:
        avg_speed = elapsed / len(batch_embeddings)
    else:
        avg_speed = "unknown"

    comparison = {
        "qwen3-embedding-8B": {
            "dimension": dimension,
            "normalized": is_normalized,
            "norm": float(norm),
            "speed_per_doc": avg_speed if isinstance(avg_speed, str) else f"{avg_speed:.3f}초",
            "recommended_distance": "cosine" if is_normalized else "l2"
        },
        "mxbai-embed-large": {
            "dimension": 1024,
            "normalized": True,
            "norm": 1.0,
            "speed_per_doc": "unknown",
            "recommended_distance": "cosine"
        }
    }

    print("\n비교 결과:")
    print(json.dumps(comparison, indent=2, ensure_ascii=False))

    # 6. 전환 가이드
    print("\n" + "=" * 60)
    print("전환 가이드")
    print("=" * 60)

    if dimension == 1024:
        print("✓ 차원 동일 (1024) → DB 재구축 불필요")
    else:
        print(f"⚠ 차원 다름 ({dimension} vs 1024) → DB 재구축 필수")
        print(f"  - 재구축 명령: python re_embed_documents.py")

    if is_normalized and dimension == 1024:
        print("✓ 최적 설정: 현재 그대로 사용 가능")
    elif is_normalized and dimension != 1024:
        print(f"⚠ 설정 변경 권장:")
        print(f"  1. config.json → embedding_model: qwen3-embedding-8B")
        print(f"  2. config.py에 chroma_distance_function: cosine 추가")
        print(f"  3. DB 재구축")
    else:
        print(f"⚠ 설정 변경 필요:")
        print(f"  1. config.json → embedding_model: qwen3-embedding-8B")
        print(f"  2. DB 재구축 (거리 함수는 l2 유지)")

    # 청크 크기 검증
    print("\n청크 크기 검증:")
    current_chunk_size = 1500  # config.py 기본값
    estimated_tokens = current_chunk_size * 0.75  # 한글/영문 혼합

    print(f"  - 현재 chunk_size: {current_chunk_size} 문자")
    print(f"  - 예상 토큰 수: {estimated_tokens:.0f} 토큰")
    print(f"  - qwen3 최대 시퀀스: (모델 문서 확인 필요)")

    if estimated_tokens > 512:
        print(f"  ⚠ qwen3가 512 토큰 제한이면 chunk_size 축소 필요")
        print(f"    권장: chunk_size = 600 (≈450 토큰)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        check_qwen3_properties()
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
