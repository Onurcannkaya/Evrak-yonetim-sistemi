"""
Evrak Yönetim Sistemi — Arka Plan İş Parçacıkları
OCR ve Tablo OCR işlemlerini ana iş parçacığını bloklamadan çalıştırır.
"""
from PyQt6.QtCore import QThread, pyqtSignal


class WorkerThread(QThread):
    """Tekli belge OCR iş parçacığı."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, document_path, analyzer):
        super().__init__()
        self.document_path = document_path
        self.analyzer = analyzer

    def run(self):
        try:
            result = self.analyzer.analyze_document(self.document_path)
            if "error" in result and result["error"]:
                self.error.emit(result["error"])
            else:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class TableWorkerThread(QThread):
    """Tablo OCR için iş parçacığı."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, path, analyzer):
        super().__init__()
        self.path = path
        self.analyzer = analyzer

    def run(self):
        try:
            result = self.analyzer.analyze_table_document(self.path)
            if "error" in result and result["error"]:
                self.error.emit(result["error"])
            else:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
