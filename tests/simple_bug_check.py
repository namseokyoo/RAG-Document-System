import chromadb

c = chromadb.PersistentClient(path='data/chroma_db')
coll = c.get_collection(name='documents')
data = coll.get(include=['metadatas'])

bugs = [m for m in data['metadatas'] if m.get('file_name', '').endswith('.pptx') and m.get('page_number') != m.get('slide_number')]

print(f"PPTX bugs found: {len(bugs)}")
for m in bugs[:10]:
    print(f"  {m['file_name']}: page={m.get('page_number')}, slide={m.get('slide_number')}, chunk={m.get('chunk_index')}")

pdf_count = len([m for m in data['metadatas'] if m.get('file_name', '').endswith('.pdf')])
pdf_all_sequential = all(
    m.get('page_number') == m.get('chunk_index') + 1
    for m in data['metadatas']
    if m.get('file_name', '').endswith('.pdf')
)

print(f"\nPDF chunks: {pdf_count}")
print(f"All PDF page_numbers = chunk_index + 1: {pdf_all_sequential}")
