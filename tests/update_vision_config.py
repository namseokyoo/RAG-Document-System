from config import ConfigManager

cm = ConfigManager()

# Vision API 설정을 LLM과 동일하게 설정
cm.update('vision_api_key', cm.get('llm_api_key'))
cm.save_config(cm.config)

print("Vision API 설정 저장 완료")
print(f"  vision_api_type: {cm.get('vision_api_type')}")
print(f"  vision_model: {cm.get('vision_model')}")
print(f"  vision_api_key: {'설정됨' if cm.get('vision_api_key') else '없음'}")
