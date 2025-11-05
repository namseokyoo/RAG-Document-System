"""Fix emoji encoding issues"""
# Replace emojis
replacements = {
    '✅': '[OK]',
    '❌': '[NG]',
    '⚠️': '[WARN]',
    '✓': '[OK]',
    '📊': '[STAT]',
    '📄': '[FILE]'
}

files = [
    'test_vision_prompt_optimization.py',
    'utils/pptx_chunking_engine.py'
]

for filepath in files:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        for emoji, replacement in replacements.items():
            content = content.replace(emoji, replacement)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f'Emojis removed from {filepath}')
    except Exception as e:
        print(f'Error processing {filepath}: {e}')
