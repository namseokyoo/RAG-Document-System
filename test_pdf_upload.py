from utils.document_processor import DocumentProcessor
from utils.vector_store import VectorStoreManager
from config import ConfigManager

# 설정 로드
config = ConfigManager().get_all()

# 문서 처리기 및 벡터 저장소 초기화
doc_processor = DocumentProcessor(config['chunk_size'], config['chunk_overlap'])
vector_store = VectorStoreManager(
    embedding_base_url=config['embedding_base_url'],
    embedding_model=config['embedding_model']
)

# PDF 파일 처리
file_path = 'data/uploaded_files/I-7장.pdf'
print(f'PDF 파일 처리 시작: {file_path}')
chunks = doc_processor.process_document(file_path, 'I-7장.pdf', 'pdf')
print(f'청크 수: {len(chunks)}')

# 벡터 저장소에 추가
print('벡터 저장소에 저장 중...')
success = vector_store.add_documents(chunks)
print(f'저장 결과: {success}')
print('완료!')

