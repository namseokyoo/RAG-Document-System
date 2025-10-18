from utils.vector_store import VectorStoreManager
from config import ConfigManager

config = ConfigManager().get_all()
vector_store = VectorStoreManager(
    embedding_base_url=config['embedding_base_url'],
    embedding_model=config['embedding_model']
)

# 벡터 저장소에서 검색 테스트
print("벡터 저장소 검색 테스트 시작...")
results = vector_store.similarity_search('I-7장 주요 내용', k=3)
print(f'검색 결과 수: {len(results)}')

for i, doc in enumerate(results):
    print(f'\n=== 결과 {i+1} ===')
    print(f'내용: {doc.page_content[:200]}...')
    print(f'메타데이터: {doc.metadata}')
    print('---')

if len(results) == 0:
    print("⚠️ 검색 결과가 없습니다. 벡터 저장소가 비어있을 수 있습니다.")

