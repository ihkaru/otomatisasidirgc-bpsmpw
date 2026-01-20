import time

from .logging_utils import log_info, log_warn
from .settings import (
    AUTO_LOGIN_RESULT_TIMEOUT_S,
    BLOCK_UI_SELECTOR,
    HASIL_GC_LABELS,
    LOGIN_PATH,
    MATCHAPRO_HOST,
    SSO_HOST,
    TARGET_URL,
)


class ActivityMonitor:
    def __init__(self, page, idle_timeout_ms, stop_event=None, timeout_scale=1.0):
        self.page = page
        self.idle_timeout_s = idle_timeout_ms / 1000
        self.last_activity = time.monotonic()
        self.stop_event = stop_event
        self.timeout_scale = timeout_scale if timeout_scale and timeout_scale > 0 else 1.0

    def _check_stop(self):
        if self.stop_event and self.stop_event.is_set():
            raise RuntimeError("Run stopped by user.")

    def mark_activity(self, _reason=None):
        self.last_activity = time.monotonic()

    def idle_check(self):
        self._check_stop()
        if time.monotonic() - self.last_activity > self.idle_timeout_s:
            raise RuntimeError(
                "Idle timeout reached (5 minutes without activity)."
            )

    def scale_timeout(self, timeout_s):
        if timeout_s is None:
            return None
        return timeout_s * self.timeout_scale

    def wait_for_condition(self, condition, timeout_s=None, poll_ms=500):
        timeout_s = self.scale_timeout(timeout_s)
        start = time.monotonic()
        while True:
            if condition():
                return True
            if timeout_s is not None and time.monotonic() - start > timeout_s:
                return False
            self.idle_check()
            self.page.wait_for_timeout(poll_ms)

    def bot_click(self, selector_or_locator):
        self._check_stop()
        self.mark_activity("bot")
        if isinstance(selector_or_locator, str):
            self.page.click(selector_or_locator)
        else:
            selector_or_locator.click()

    def bot_fill(self, selector_or_locator, value):
        self._check_stop()
        self.mark_activity("bot")
        val_str = "" if value is None else str(value)
        if hasattr(selector_or_locator, "fill"):
            selector_or_locator.fill(val_str)
        else:
            self.page.fill(selector_or_locator, val_str)

    def bot_select_option(self, selector, **kwargs):
        self._check_stop()
        self.mark_activity("bot")
        self.page.select_option(selector, **kwargs)

    def bot_goto(self, url):
        self._check_stop()
        self.mark_activity("bot")
        self.page.goto(url, wait_until="domcontentloaded")


def install_user_activity_tracking(page, mark_activity):
    page.expose_function("reportActivity", lambda: mark_activity("user"))
    page.add_init_script(
        """
        (() => {
          function isRelevantInput(target) {
            if (!target) return false;
            const id = (target.id || "").toLowerCase();
            const name = (target.name || "").toLowerCase();
            const autocomplete = (target.autocomplete || "").toLowerCase();
            if (id === "username" || id === "password") return true;
            if (name === "username" || name === "password") return true;
            if (autocomplete === "one-time-code") return true;
            const markers = ["otp", "verif", "kode", "mfa"];
            return markers.some((marker) => id.includes(marker) || name.includes(marker));
          }

          function reportIfCredentialInput(event) {
            const target = event.target;
            if (!isRelevantInput(target)) return;
            if (window.reportActivity) {
              window.reportActivity();
            }
          }
          document.addEventListener("input", reportIfCredentialInput, true);
          document.addEventListener("change", reportIfCredentialInput, true);
        })();
        """
    )


def ensure_on_dirgc(
    page,
    monitor,
    use_saved_credentials,
    credentials,
):
    def is_on_target():
        # Strict check: URL correct AND specific element present indicating app loaded
        # This prevents "false start" during client-side redirects to login
        if not page.url.startswith(TARGET_URL):
            return False
            
        # Check for search filter or card list presence
        # We use a quick check without waiting too long
        return page.locator("#search-idsbr").count() > 0 or page.locator(".usaha-card").count() > 0

    def is_on_login_page():
        return MATCHAPRO_HOST in page.url and LOGIN_PATH in page.url

    def is_on_matchapro():
        return page.url.startswith(f"https://{MATCHAPRO_HOST}") or page.url.startswith(f"http://{MATCHAPRO_HOST}")

    def is_on_sso_login():
        if SSO_HOST in page.url:
            return True
        return page.locator("#kc-login").count() > 0

    def is_on_otp_challenge():
        if not is_on_sso_login():
            return False
        otp_selectors = [
            "input[autocomplete='one-time-code']",
            "input[name*='otp']",
            "input[id*='otp']",
            "input[name*='verif']",
            "input[id*='verif']",
            "input[name*='kode']",
            "input[id*='kode']",
        ]
        for selector in otp_selectors:
            locator = page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible():
                return True
        text_markers = [
            "OTP",
            "Kode OTP",
            "kode otp",
            "verification code",
            "kode verifikasi",
        ]
        for marker in text_markers:
            locator = page.locator(f"text={marker}")
            if locator.count() > 0 and locator.first.is_visible():
                return True
        return False

    def click_if_present(selector):
        locator = page.locator(selector)
        if locator.count() == 0:
            return False
        monitor.bot_click(locator.first)
        return True

    def attempt_auto_login(username, password):
        if not username or not password:
            log_warn(
                "Saved credentials missing; switching to manual login."
            )
            return False

        # Try robust filling logic
        # Helper to find input with multiple strategies
        def find_input_in_context(p, ids, names, placeholders):
            for i in ids:
                l = p.locator(f"#{i}")
                if l.count() > 0 and l.first.is_visible(): return l.first
            for n in names:
                l = p.locator(f"input[name='{n}']")
                if l.count() > 0 and l.first.is_visible(): return l.first
            for ph in placeholders:
                l = p.get_by_placeholder(ph)
                if l.count() > 0 and l.first.is_visible(): return l.first
            return None

        # Retry finding fields for up to 10 seconds
        start_find = time.monotonic()
        user_loc = None
        pass_loc = None
        
        while time.monotonic() - start_find < 10:
            # Try main page first
            user_loc = find_input_in_context(page, ["username", "user"], ["username", "user", "email"], ["Username", "Username or email"])
            pass_loc = find_input_in_context(page, ["password", "pwd"], ["password", "pwd"], ["Password"])

            # If not found, check frames
            if not user_loc or not pass_loc:
                 for frame in page.frames:
                     if not user_loc: user_loc = find_input_in_context(frame, ["username"], ["username"], ["Username"])
                     if not pass_loc: pass_loc = find_input_in_context(frame, ["password"], ["password"], ["Password"])
                     if user_loc and pass_loc: break
            
            if user_loc and pass_loc:
                break
            
            page.wait_for_timeout(500)
        
        if not user_loc or not pass_loc:
             log_warn("Login fields not found after waiting; switching to manual login.")
             return False

        # Attempt fill
        try:
             # Remove readonly if possible (JS might fail on frames if cross-origin, so wrap in try)
             try:
                 user_loc.evaluate("el => el.removeAttribute('readonly')")
                 pass_loc.evaluate("el => el.removeAttribute('readonly')")
             except:
                 pass
             
             # Use generic fill to avoid activity tracking issues if needed, but bot_fill handles it
             monitor.bot_fill(user_loc, username)
             monitor.bot_fill(pass_loc, password)
             
             # Click login
             login_btn = None
             # Try to find button in same context as user field if possible? 
             # Simpler: just search everywhere like before
             
             # Search button
             possible_btns = ["#kc-login", "input[type='submit']", "button[type='submit']"]
             for sel in possible_btns:
                 l = page.locator(sel)
                 if l.count() > 0:
                     login_btn = l.first
                     break
            
             if login_btn:
                  monitor.bot_click(login_btn)
             else:
                  pass_loc.press("Enter")
             
             # Check for immediate login errors or success
             error_selectors = [
                 "#input-error",
                 "#kc-error-message",
                 ".kc-feedback-text",
                 ".alert-error",
                 ".pf-c-alert__title",
             ]
             
             start = time.monotonic()
             while True:
                 if is_on_matchapro():
                     return True
                 
                 for selector in error_selectors:
                     # Check main page
                     if page.locator(selector).count() > 0 and page.locator(selector).first.is_visible():
                         log_warn("Login error detected on page.")
                         return False
                     # Check frames just in case
                     for frame in page.frames:
                         if frame.locator(selector).count() > 0 and frame.locator(selector).first.is_visible():
                            log_warn("Login error detected in frame.")
                            return False

                 if time.monotonic() - start > monitor.scale_timeout(5):
                     # Assume success if no error appeared quickly, let the caller wait for full load
                     return True
                 
                 page.wait_for_timeout(500)

        except Exception as e:
             log_warn(f"Error during auto-fill: {e}")
             return False

        error_selectors = [
            "#input-error",
            "#kc-error-message",
            ".kc-feedback-text",
            ".alert-error",
            ".pf-c-alert__title",
        ]

        start = time.monotonic()
        while True:
            if is_on_matchapro():
                return True
            for selector in error_selectors:
                locator = page.locator(selector)
                if locator.count() > 0 and locator.first.is_visible():
                    return False
            if time.monotonic() - start > monitor.scale_timeout(
                AUTO_LOGIN_RESULT_TIMEOUT_S
            ):
                return False
            monitor.idle_check()
            page.wait_for_timeout(500)

    allow_autofill = use_saved_credentials
    autofill_attempted = False
    username, password = credentials or (None, None)

    monitor.bot_goto(TARGET_URL)

    while True:
        monitor.idle_check()  # Ensure we check for stop requests every cycle
        
        if is_on_target():
            log_info("On target page.", url=page.url)
            return

        if is_on_login_page():
            if click_if_present("#login-sso"):
                log_info("Redirecting to SSO login.")
                monitor.wait_for_condition(
                    lambda: is_on_sso_login() or is_on_matchapro(),
                    timeout_s=30,
                )
                continue
            monitor.wait_for_condition(
                lambda: page.locator("#login-sso").count() > 0
                or not is_on_login_page(),
                timeout_s=10,
            )
            continue

        if is_on_sso_login():
            if allow_autofill and not autofill_attempted:
                autofill_attempted = True
                if attempt_auto_login(username, password):
                    monitor.wait_for_condition(is_on_matchapro, timeout_s=60)
                    continue
                allow_autofill = False
                log_warn("Auto-fill login failed; switching to manual login.")

            if is_on_otp_challenge():
                log_info("OTP required; waiting for manual input.")
            else:
                log_info("Waiting for manual login.")
            monitor.wait_for_condition(is_on_matchapro)
            continue

        if is_on_matchapro() and not is_on_target():
            monitor.bot_goto(TARGET_URL)
            continue

        monitor.wait_for_condition(lambda: False, timeout_s=2)


def is_visible(page, selector):
    locator = page.locator(selector)
    return locator.count() > 0 and locator.first.is_visible()


def wait_for_block_ui_clear(page, monitor, timeout_s=15):
    try:
        monitor.wait_for_condition(
            lambda: page.locator(BLOCK_UI_SELECTOR).count() == 0
            or not is_visible(page, BLOCK_UI_SELECTOR),
            timeout_s=timeout_s,
        )
    except RuntimeError:
        # If still there after timeout, try to remove it aggressively
        log_warn("BlockUI stuck; attempting to force remove.")
        page.evaluate(
            f"""
            const el = document.querySelector('{BLOCK_UI_SELECTOR}');
            if (el) el.remove();
            """
        )


def ensure_filter_panel_open(page, monitor):
    if is_visible(page, "#search-idsbr"):
        return
    toggle = page.locator("#toggle-filter")
    if toggle.count() > 0:
        wait_for_block_ui_clear(page, monitor, timeout_s=5)
        monitor.bot_click(toggle.first)
        monitor.wait_for_condition(
            lambda: is_visible(page, "#search-idsbr"), timeout_s=10
        )


def apply_filter(page, monitor, idsbr, nama_usaha, alamat):
    ensure_filter_panel_open(page, monitor)

    def get_results_snapshot():
        header_locator = page.locator(".usaha-card-header")
        count = header_locator.count()
        first_text = ""
        last_text = ""
        if count > 0:
            try:
                first_text = header_locator.first.inner_text().strip()
            except Exception:
                first_text = ""
            if count > 1:
                try:
                    last_text = (
                        header_locator.nth(count - 1)
                        .inner_text()
                        .strip()
                    )
                except Exception:
                    last_text = ""
            else:
                last_text = first_text
        return count, first_text, last_text

    def results_changed(previous_snapshot):
        return get_results_snapshot() != previous_snapshot

    def wait_for_results(previous_snapshot, timeout_s=15):
        monitor.wait_for_condition(
            lambda: is_visible(page, ".empty-state")
            or is_visible(page, ".no-data")
            or is_visible(page, ".no-results")
            or results_changed(previous_snapshot),
            timeout_s=timeout_s,
        )
        wait_for_block_ui_clear(page, monitor, timeout_s=timeout_s)
        return page.locator(".usaha-card-header").count()

    def retry_results_if_slow(count, timeout_s=5):
        if count <= 1:
            return count
        previous_snapshot = get_results_snapshot()
        updated = monitor.wait_for_condition(
            lambda: is_visible(page, ".empty-state")
            or is_visible(page, ".no-data")
            or is_visible(page, ".no-results")
            or results_changed(previous_snapshot),
            timeout_s=timeout_s,
        )
        if not updated:
            return count
        wait_for_block_ui_clear(page, monitor, timeout_s=timeout_s)
        return page.locator(".usaha-card-header").count()

    def set_filter_values(idsbr_value, nama_value, alamat_value):
        monitor.mark_activity("bot")
        page.evaluate(
            """
            ({ idsbrValue, namaValue, alamatValue }) => {
              const setValue = (selector, value) => {
                const input = document.querySelector(selector);
                if (!input) return;
                input.value = value || "";
              };

              setValue("#search-idsbr", idsbrValue);
              setValue("#search-nama", namaValue);
              setValue("#search-alamat", alamatValue);

              const dispatch = (selector) => {
                const input = document.querySelector(selector);
                if (!input) return;
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
              };

              dispatch("#search-idsbr");
              dispatch("#search-nama");
              dispatch("#search-alamat");
            }
            """,
            {
                "idsbrValue": idsbr_value or "",
                "namaValue": nama_value or "",
                "alamatValue": alamat_value or "",
            },
        )

    def search_with(idsbr_value, nama_value, alamat_value):
        previous_snapshot = get_results_snapshot()
        set_filter_values(idsbr_value, nama_value, alamat_value)
        monitor.wait_for_condition(lambda: False, timeout_s=0.5)
        return wait_for_results(previous_snapshot)

    if idsbr:
        count = search_with(idsbr, "", "")
        if count > 1:
            log_info(
                "Results not unique; rechecking for slow loading.",
                count=count,
            )
            count = retry_results_if_slow(count)
        if count == 1:
            return count
        if nama_usaha or alamat:
            if count == 0:
                log_warn(
                    "IDSBR not found; retry with idsbr + nama_usaha + alamat."
                )
            else:
                log_warn(
                    "Multiple results for IDSBR; retry with idsbr + nama_usaha + alamat.",
                    count=count,
                )
            return search_with(idsbr, nama_usaha, alamat)
        return count

    return search_with("", nama_usaha, alamat)


def hasil_gc_select(page, monitor, code):
    if code is None:
        return False
    
    # 1. Wait for element
    if not monitor.wait_for_condition(
        lambda: page.locator("#tt_hasil_gc").count() > 0 and page.locator("#tt_hasil_gc").first.is_visible(), 
        timeout_s=5
    ):
        log_warn("Dropdown Hasil GC not found/visible.")
        return False

    value_str = str(code)
    # Mapping fix for "Tidak Ditemukan" which is code 0 but value 99 in HTML
    if value_str == "0":
        value_str = "99"

    label = HASIL_GC_LABELS.get(code)
    
    # 2. Try Standard Playwright Select with FORCE
    try:
        # Pass force=True to bypass visibility checks if element is obscured/hidden
        monitor.bot_select_option("#tt_hasil_gc", value=value_str, force=True)
        return True
    except Exception as e:
        # log_warn(f"Standard select failed: {e}")
        pass # Fallback
        
    if label:
        try:
            monitor.bot_select_option("#tt_hasil_gc", label=label, force=True)
            return True
        except Exception:
            pass

    # 3. Ninja Mode: JavaScript Injection (Force Value)
    try:
        log_warn(f"Force selecting Hasil GC: {value_str} via JS")
        page.evaluate(
            """
            (value) => {
                const select = document.querySelector("#tt_hasil_gc");
                if (select) {
                    select.value = value;
                    select.dispatchEvent(new Event('change', {bubbles: true}));
                    select.dispatchEvent(new Event('input', {bubbles: true}));
                    // Trigger jQuery change if present (common in older admin themes)
                    if (window.jQuery) {
                        window.jQuery(select).trigger('change');
                    }
                }
            }
            """,
            value_str
        )
        # Verify if value stuck
        current_val = page.locator("#tt_hasil_gc").input_value()
        return str(current_val) == value_str
    except Exception as e:
        log_warn(f"JS Force Select failed: {e}")
        return False
