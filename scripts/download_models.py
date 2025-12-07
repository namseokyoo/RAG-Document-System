#!/usr/bin/env python3
"""
로컬 모델 캐시 다운로드 스크립트
외부망에서 실행하여 모델들을 로컬에 저장
"""

import os
import sys
from pathlib import Path
from sentence_transformers import CrossEncoder
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 모델 정보
MODELS = {
    "multilingual-mini": {
        "huggingface_id": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "local_path": "models/reranker-mini",
        "size": "22MB",
        "description": "빠르고 가벼운 다국어 Re-ranker"
    },
    "multilingual-base": {
        "huggingface_id": "cross-encoder/ms-marco-MiniLM-L-12-v2", 
        "local_path": "models/reranker-base",
        "size": "133MB",
        "description": "더 정확한 다국어 Re-ranker"
    }
}

def download_model(model_name: str, force_download: bool = False) -> bool:
    """
    특정 모델을 다운로드하고 로컬에 저장
    
    Args:
        model_name: 다운로드할 모델 이름
        force_download: 기존 모델 덮어쓰기 여부
    
    Returns:
        bool: 다운로드 성공 여부
    """
    if model_name not in MODELS:
        logger.error(f"지원하지 않는 모델: {model_name}")
        return False
    
    model_info = MODELS[model_name]
    local_path = Path(model_info["local_path"])
    huggingface_id = model_info["huggingface_id"]
    
    # 로컬 디렉토리 생성
    local_path.mkdir(parents=True, exist_ok=True)
    
    # 기존 모델 확인
    if local_path.exists() and any(local_path.iterdir()) and not force_download:
        logger.info(f"✅ {model_name} 모델이 이미 존재합니다: {local_path}")
        return True
    
    try:
        logger.info(f"📥 {model_name} 모델 다운로드 시작...")
        logger.info(f"   - HuggingFace ID: {huggingface_id}")
        logger.info(f"   - 로컬 경로: {local_path}")
        logger.info(f"   - 크기: {model_info['size']}")
        logger.info(f"   - 설명: {model_info['description']}")
        
        # 모델 다운로드 및 로컬 저장
        model = CrossEncoder(huggingface_id)
        model.save(str(local_path))
        
        logger.info(f"✅ {model_name} 모델 다운로드 완료!")
        return True
        
    except Exception as e:
        logger.error(f"❌ {model_name} 모델 다운로드 실패: {e}")
        return False

def download_all_models(force_download: bool = False) -> bool:
    """
    모든 모델을 다운로드
    
    Args:
        force_download: 기존 모델 덮어쓰기 여부
    
    Returns:
        bool: 모든 모델 다운로드 성공 여부
    """
    logger.info("🚀 모든 Re-ranker 모델 다운로드 시작...")
    
    success_count = 0
    total_count = len(MODELS)
    
    for model_name in MODELS.keys():
        if download_model(model_name, force_download):
            success_count += 1
        else:
            logger.warning(f"⚠️ {model_name} 모델 다운로드 실패")
    
    logger.info(f"📊 다운로드 결과: {success_count}/{total_count} 성공")
    
    if success_count == total_count:
        logger.info("🎉 모든 모델 다운로드 완료!")
        return True
    else:
        logger.warning("⚠️ 일부 모델 다운로드 실패")
        return False

def check_models() -> None:
    """로컬 모델 상태 확인"""
    logger.info("🔍 로컬 모델 상태 확인...")
    
    for model_name, model_info in MODELS.items():
        local_path = Path(model_info["local_path"])
        
        if local_path.exists() and any(local_path.iterdir()):
            logger.info(f"✅ {model_name}: {local_path} (존재)")
        else:
            logger.warning(f"❌ {model_name}: {local_path} (없음)")

def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="로컬 모델 캐시 다운로드")
    parser.add_argument("--model", choices=list(MODELS.keys()), 
                       help="다운로드할 특정 모델")
    parser.add_argument("--all", action="store_true", 
                       help="모든 모델 다운로드")
    parser.add_argument("--check", action="store_true", 
                       help="로컬 모델 상태 확인")
    parser.add_argument("--force", action="store_true", 
                       help="기존 모델 덮어쓰기")
    
    args = parser.parse_args()
    
    if args.check:
        check_models()
    elif args.model:
        success = download_model(args.model, args.force)
        sys.exit(0 if success else 1)
    elif args.all:
        success = download_all_models(args.force)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
