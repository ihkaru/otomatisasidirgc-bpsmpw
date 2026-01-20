
import threading
from PyQt5.QtCore import QThread, pyqtSignal
from dirgc.cli import run_dirgc
from dirgc.logging_utils import set_log_handler

class RunWorker(QThread):
    progress = pyqtSignal(int, int, int)
    log_emitted = pyqtSignal(str)

    def __init__(self, config, sso_page=None):
        super().__init__()
        self._config = config
        self._stop_event = threading.Event()
        self._close_event = threading.Event()
        self._sso_page = sso_page

    def run(self):
        set_log_handler(self.handle_log)
        try:
            creds = None
            if self._sso_page and not self._config.manual_only:
                creds_dict = self._sso_page.get_credentials()
                if creds_dict:
                    creds = (creds_dict.get("username"), creds_dict.get("password"))
            
            # Fallback: if credentials are None but not in manual mode, try loading from file
            # This handles case where SsoPage might not have been visited to load state
            if creds is None and not self._config.manual_only:
                from dirgc.credentials import load_credentials
                from dirgc.settings import DEFAULT_CREDENTIALS_FILE
                creds = load_credentials(DEFAULT_CREDENTIALS_FILE)

            run_dirgc(
                headless=self._config.headless,
                manual_only=self._config.manual_only,
                excel_file=self._config.excel_file,
                start_row=self._config.start_row
                if self._config.range_enabled
                else None,
                end_row=self._config.end_row if self._config.range_enabled else None,
                idle_timeout_ms=self._config.idle_timeout_ms,
                web_timeout_s=self._config.web_timeout_s,
                keep_open=self._config.keep_open,
                credentials=creds,
                stop_event=self._stop_event,
                progress_callback=self._emit_progress,
                wait_for_close=self._wait_for_close
                if self._config.keep_open
                else None,
            )
        except Exception:
            raise
        finally:
            set_log_handler(None)

    def _wait_for_close(self):
        # We need to signal the UI to maybe show a "release" button or just wait?
        # In the original app.py, it emits request_close and waits for close_event.
        # But for simplification, we might just wait on the event.
        # However, we need a way to tell the UI that we are waiting.
        # Let's add a signal for that if needed, or just rely on the fact that
        # the browser won't close until we set the event.
        self._close_event.wait()

    def release_close(self):
        self._close_event.set()

    def request_stop(self):
        self._stop_event.set()

    def handle_log(self, line, **kwargs):
        self.log_emitted.emit(line)
        if kwargs.get('spacer'):
            self.log_emitted.emit("")
        if kwargs.get('divider'):
            self.log_emitted.emit("-" * 72) # Match DIVIDER_LEN

    def _emit_progress(self, processed, total, excel_row):
        self.progress.emit(int(processed), int(total), int(excel_row))
