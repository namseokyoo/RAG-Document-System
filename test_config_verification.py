"""Configuration verification test"""
from utils.pdf_chunking_engine import PDFChunkingEngine
from config import ConfigManager

config_mgr = ConfigManager()
config = config_mgr.get_all()
engine = PDFChunkingEngine(config)

print("=" * 80)
print("PDF Engine Configuration Verification")
print("=" * 80)
print(f"Vision enabled: {engine.enable_vision}")
print(f"Hybrid enabled: {engine.enable_hybrid}")
print(f"Poppler path: {config.get('poppler_path')}")
print(f"PDF DPI: {config.get('pdf_dpi')}")
print(f"Vision detail: {config.get('pdf_vision_detail')}")
print()

# Verify Poppler is accessible
import os
if config.get('poppler_path'):
    pdftoppm_path = os.path.join(config.get('poppler_path'), 'pdftoppm.exe')
    if os.path.exists(pdftoppm_path):
        print(f"[OK] Poppler pdftoppm.exe found: {pdftoppm_path}")
    else:
        print(f"[ERROR] Poppler pdftoppm.exe NOT found at: {pdftoppm_path}")
else:
    print("[WARN] Poppler path not configured - will use system PATH")

print("=" * 80)
print("Configuration verification complete!")
print("=" * 80)
