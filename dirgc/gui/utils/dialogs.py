
from PyQt5.QtWidgets import QMessageBox

class DialogHelper:
    @staticmethod
    def confirm(parent, title, message):
        w = QMessageBox(parent)
        w.setWindowTitle(title)
        w.setText(message)
        w.setIcon(QMessageBox.Question)
        w.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        w.setDefaultButton(QMessageBox.No)
        return w.exec_() == QMessageBox.Yes

    @staticmethod
    def resume_dialog(parent, last_row):
        message = (
            f"Ditemukan pengerjaan terakhir sampai baris {last_row}.\n\n"
            f"Klik Yes untuk LANJUT dari baris {last_row + 1}.\n"
            f"Klik No untuk mulai sesuai settingan di layar."
        )
        title = "Lanjutkan?"
        
        w = QMessageBox(parent)
        w.setWindowTitle(title)
        w.setText(message)
        w.setIcon(QMessageBox.Question)
        btn_resume = w.addButton(f"Lanjut (Baris {last_row + 1})", QMessageBox.YesRole)
        btn_manual = w.addButton("Sesuai Settingan", QMessageBox.NoRole)
        w.addButton("Batal", QMessageBox.RejectRole)
        w.exec_()
        
        if w.clickedButton() == btn_resume:
            return "resume"
        elif w.clickedButton() == btn_manual:
            return "manual"
        return "cancel"
