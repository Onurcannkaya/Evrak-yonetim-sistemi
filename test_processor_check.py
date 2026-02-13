import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from document_processor import DocumentProcessor
    import pytesseract
    
    print("Initializing DocumentProcessor...")
    processor = DocumentProcessor()
    
    print(f"Tesseract Path: {pytesseract.pytesseract.tesseract_cmd}")
    print(f"Tessdata Prefix: {os.environ.get('TESSDATA_PREFIX')}")
    
    if os.path.exists(pytesseract.pytesseract.tesseract_cmd):
        print("✅ Tesseract executable found.")
    else:
        print("❌ Tesseract executable NOT found.")
        
    tessdata = os.environ.get('TESSDATA_PREFIX')
    if tessdata and os.path.exists(tessdata):
        print("✅ Tessdata directory found.")
    else:
        print("❌ Tessdata directory NOT found.")

    print("\nChecking dictionary...")
    print(f"Dictionary size: {len(processor.municipal_dictionary)}")
    if "FARKIS" in processor.municipal_dictionary:
        print("✅ Dictionary 'FARKIS' -> 'ŞARKIŞLA' check passed.")
        
    print("\n✅ DocumentProcessor initialization successful.")
    
except Exception as e:
    print(f"\n❌ Verification Failed: {e}")
    import traceback
    traceback.print_exc()
