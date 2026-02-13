"""
PyQt6 Path Encoding Test
Tests if Path().resolve() fixes Turkish character encoding issue
"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QFileDialog, QLabel, QVBoxLayout, QWidget
from PIL import Image
import cv2

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt6 Path Test")
        self.resize(400, 200)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        self.label = QLabel("Dosya seçin...")
        layout.addWidget(self.label)
        
        btn = QPushButton("Dosya Seç")
        btn.clicked.connect(self.test_path)
        layout.addWidget(btn)
        
    def test_path(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Test", "",
            "Images (*.jpg *.png *.pdf)")
        
        if not path:
            return
            
        # ORIGINAL (BROKEN):
        self.label.setText(f"Original path: {path}\n")
        
        # FIX: Normalize with pathlib
        normalized = str(Path(path).resolve())
        self.label.setText(self.label.text() + f"\nNormalized: {normalized}\n")
        
        # Test with PIL
        try:
            img = Image.open(normalized)
            self.label.setText(self.label.text() + f"\n✅ PIL OK: {img.size}")
        except Exception as e:
            self.label.setText(self.label.text() + f"\n❌ PIL FAIL: {e}")
        
        # Test with OpenCV
        try:
            img_cv = cv2.imread(normalized)
            if img_cv is not None:
                self.label.setText(self.label.text() + f"\n✅ OpenCV OK: {img_cv.shape}")
            else:
                self.label.setText(self.label.text() + "\n❌ OpenCV returned None")
        except Exception as e:
            self.label.setText(self.label.text() + f"\n❌ OpenCV FAIL: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
