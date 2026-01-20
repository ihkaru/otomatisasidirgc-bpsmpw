from .browser import (
    apply_filter,
    ensure_on_dirgc,
    hasil_gc_select,
    is_visible,
    wait_for_block_ui_clear,
)
from .excel import load_excel_rows
from .logging_utils import log_error, log_info, log_warn
from .matching import select_matching_card
from .run_logs import build_run_log_path, write_run_log
from .settings import TARGET_URL


def process_excel_rows(
    page,
    monitor,
    excel_file,
    use_saved_credentials,
    credentials,
    start_row=None,
    end_row=None,
    progress_callback=None,
):
    run_log_path = build_run_log_path()
    run_log_rows = []
    try:
        rows = load_excel_rows(excel_file)
    except Exception as exc:
        log_error("Failed to load Excel file.")
        run_log_rows.append(
            {
                "no": 0,
                "idsbr": "",
                "nama_usaha": "",
                "alamat": "",
                "keberadaanusaha_gc": "",
                "latitude": "",
                "longitude": "",
                "status": "error",
                "catatan": str(exc),
            }
        )
        write_run_log(run_log_rows, run_log_path)
        log_info("Run log saved.", path=str(run_log_path))
        return
    if not rows:
        log_warn("No rows found in Excel file.")
        write_run_log(run_log_rows, run_log_path)
        log_info("Run log saved.", path=str(run_log_path))
        return

    total_rows = len(rows)
    start_row = 1 if start_row is None else start_row
    end_row = total_rows if end_row is None else end_row
    if start_row < 1 or end_row < 1:
        log_error(
            "Start/end row must be >= 1.",
            start_row=start_row,
            end_row=end_row,
        )
        write_run_log(run_log_rows, run_log_path)
        log_info("Run log saved.", path=str(run_log_path))
        return
    if start_row > end_row:
        log_warn(
            "Start row is greater than end row; nothing to process.",
            start_row=start_row,
            end_row=end_row,
        )
        write_run_log(run_log_rows, run_log_path)
        log_info("Run log saved.", path=str(run_log_path))
        return
    if start_row > total_rows:
        log_warn(
            "Start row exceeds total rows; nothing to process.",
            start_row=start_row,
            total=total_rows,
        )
        write_run_log(run_log_rows, run_log_path)
        log_info("Run log saved.", path=str(run_log_path))
        return
    if end_row > total_rows:
        log_warn(
            "End row exceeds total rows; clamping.",
            end_row=end_row,
            total=total_rows,
        )
        end_row = total_rows

    rows = rows[start_row - 1 : end_row]
    selected_rows = len(rows)
    stats = {
        "total": selected_rows,
        "processed": 0,
        "skipped_no_results": 0,
        "skipped_gc": 0,
        "skipped_duplikat": 0,
        "skipped_no_tandai": 0,
        "hasil_gc_set": 0,
        "hasil_gc_skipped": 0,
        "skipped": 0,
    }
    log_info(
        "Start processing rows.",
        total=selected_rows,
        start_row=start_row,
        end_row=end_row,
    )
    if progress_callback:
        try:
            progress_callback(0, selected_rows, 0)
        except Exception:
            pass

    import json
    import time
    import os
    from .settings import LAST_RUN_STATE_FILE
    from .settings import LAST_RUN_STATE_FILE
    from .run_logs import get_completed_idsbrs

    # --- RATE LIMIT DETECTION ---
    is_rate_limited = False
    rate_limit_wait = 60 # default fallback
    
    def on_response(response):
        nonlocal is_rate_limited, rate_limit_wait
        if response.status == 429:
            is_rate_limited = True
            # Try to parse Retry-After header
            try:
                headers = response.all_headers()
                # Check different casing just in case
                retry_val = headers.get("retry-after") or headers.get("Retry-After")
                if retry_val:
                    val = int(retry_val)
                    # Add small buffer +1s
                    rate_limit_wait = val + 1
                    # Cap at reasonable max, e.g. 120s
                    if rate_limit_wait > 120: rate_limit_wait = 120
            except:
                pass
            
    # Attach listener
    page.on("response", on_response)

    # Exponential Backoff State
    # USER CONFIRMED: Ban duration is 10 minutes from last request.
    # We set wait to 11 minutes (660s) to be safe.
    base_wait = 660 
    current_wait = base_wait

    def handle_rate_limit():
        nonlocal is_rate_limited, rate_limit_wait, current_wait
        if is_rate_limited:
            # Use server time if provided and larger than our base, else use our backoff
            wait_time = max(rate_limit_wait, current_wait) if rate_limit_wait > 0 else current_wait
            
            log_warn(f"⚠️ RATE LIMIT DETECTED (F5 Firewall Block).")
            
            # WAF EVASION: Clear cookies
            log_info("Clearing cookies to reset WAF session...")
            try:
                page.context.clear_cookies()
            except Exception as e:
                log_warn(f"Failed to clear cookies: {e}")

            log_info(f"Cooling down for {wait_time}s (F5 Block Duration)...")
            time.sleep(wait_time)
            
            # Increase backoff for next time if we get hit again quickly
            current_wait = min(current_wait * 2, 3600) # Cap at 1 hour

            is_rate_limited = False
            rate_limit_wait = 0 # Reset server header value
            return True 
        
        # If we successfully process row without rate limit, slowly decay backoff?
        # For simplicity, we keep it high if this run is "tainted", or we could reset after success.
        return False

    # Load history of completed IDs
    log_info("Scanning logs for completed IDsBR...")
    completed_ids = get_completed_idsbrs()
    log_info(f"Loaded {len(completed_ids)} completed IDs from history.")

    for offset, row in enumerate(rows):
        # 0. Check Rate Limit Signal from previous request
        if handle_rate_limit():
            log_info("Resuming after pause. Re-checking login state...")
            # Re-login because cookies were cleared
            ensure_on_dirgc(
                page, 
                monitor, 
                use_saved_credentials, 
                credentials
            )


        batch_index = offset + 1
        excel_row = start_row + offset
        
        idsbr = str(row["idsbr"])
        
        # Check against blacklist
        if idsbr in completed_ids:
            log_info(
                f"Skipping row (Already completed in previous runs).", 
                row=batch_index, total=selected_rows, row_excel=excel_row, idsbr=idsbr
            )
            # Emit progress even if skipped
            if progress_callback:
                progress_callback(stats["processed"], selected_rows, excel_row)
            stats["processed"] += 1
            stats["skipped"] += 1
            continue

        stats["processed"] += 1
        status = None
        note = ""

        # idsbr already str above
        nama_usaha = row["nama_usaha"]
        alamat = row["alamat"]
        latitude = row["latitude"]
        longitude = row["longitude"]
        hasil_gc = row["hasil_gc"]

        log_info(
            "Processing row.",
            _spacer=True,
            _divider=True,
            row=batch_index,
            total=selected_rows,
            row_excel=excel_row,
            idsbr=idsbr or "-",
        )
        ensure_on_dirgc(
            page,
            monitor=monitor,
            use_saved_credentials=use_saved_credentials,
            credentials=credentials,
        )

        try:
            log_info(
                "Applying filter.",
                idsbr=idsbr or "-",
                nama_usaha=nama_usaha or "-",
                alamat=alamat or "-",
            )
            result_count = apply_filter(page, monitor, idsbr, nama_usaha, alamat)
            log_info("Filter results.", count=result_count)

            selection = select_matching_card(
                page, monitor, idsbr, nama_usaha, alamat
            )
            if not selection:
                log_warn("No results found; skipping.", idsbr=idsbr or "-")
                stats["skipped_no_results"] += 1
                status = "gagal"
                note = "No results found"
                continue

            header_locator, card_scope = selection
            try:
                header_locator.scroll_into_view_if_needed()
            except Exception:
                pass
            monitor.bot_click(header_locator)

            if card_scope.count() == 0:
                card_scope = page

            if (
                card_scope.locator(".gc-badge", has_text="Sudah GC").count()
                > 0
            ):
                log_info("Skipped: Sudah GC.", idsbr=idsbr or "-")
                stats["skipped_gc"] += 1
                status = "skipped"
                note = "Sudah GC"
                continue

            if card_scope.locator(
                ".usaha-status.tidak-aktif", has_text="Duplikat"
            ).count() > 0:
                log_info("Skipped: Duplikat.", idsbr=idsbr or "-")
                stats["skipped_duplikat"] += 1
                status = "skipped"
                note = "Duplikat"
                continue

            tandai_locator = page.locator(".btn-tandai")
            if tandai_locator.count() == 0:
                log_warn(
                    "Tombol Tandai tidak ditemukan; skipping.",
                    idsbr=idsbr or "-",
                )
                stats["skipped_no_tandai"] += 1
                status = "gagal"
                note = "Tombol Tandai tidak ditemukan"
                continue
            if not tandai_locator.first.is_visible():
                log_warn(
                    "Tombol Tandai tidak terlihat; skipping.",
                    idsbr=idsbr or "-",
                )
                stats["skipped_no_tandai"] += 1
                status = "gagal"
                note = "Tombol Tandai tidak terlihat"
                continue

            wait_for_block_ui_clear(page, monitor, timeout_s=15)
            try:
                tandai_locator.first.scroll_into_view_if_needed()
            except Exception:
                pass
            try:
                monitor.bot_click(tandai_locator.first)
            except Exception as exc:
                log_warn(
                    "Tombol Tandai gagal diklik; skipping.",
                    idsbr=idsbr or "-",
                    error=str(exc),
                )
                stats["skipped_no_tandai"] += 1
                status = "gagal"
                note = "Tombol Tandai gagal diklik"
                continue
            form_ready = monitor.wait_for_condition(
                lambda: page.locator("#tt_hasil_gc").count() > 0,
                timeout_s=30,
            )
            if not form_ready:
                log_warn(
                    "Form Hasil GC tidak muncul; skipping.",
                    idsbr=idsbr or "-",
                )
                stats["skipped_no_tandai"] += 1
                status = "gagal"
                note = "Form Hasil GC tidak muncul"
                continue

            if hasil_gc_select(page, monitor, hasil_gc):
                log_info(
                    "Hasil GC set.", hasil_gc=hasil_gc, idsbr=idsbr or "-"
                )
                stats["hasil_gc_set"] += 1
            else:
                log_warn(
                    "Hasil GC tidak diisi (kode tidak valid/kosong).",
                    idsbr=idsbr or "-",
                )
                stats["hasil_gc_skipped"] += 1
                status = "gagal"
                note = "Hasil GC tidak valid/kosong"

            def safe_fill(selector, value, field_name):
                locator = page.locator(selector)
                if locator.count() == 0 or not locator.first.is_visible():
                    log_warn(
                        "Field tidak ditemukan; lewati.",
                        idsbr=idsbr or "-",
                        field=field_name,
                    )
                    return
                try:
                    current_value = locator.first.input_value()
                except Exception:
                    current_value = ""
                if current_value and str(current_value).strip():
                    return
                if not value:
                    return
                monitor.bot_fill(selector, value)

            # Manual coordinate fill log
            log_info(f"Filling coordinates: Lat={latitude}, Long={longitude}")
            safe_fill("#tt_latitude_cek_user", latitude, "latitude")
            safe_fill("#tt_longitude_cek_user", longitude, "longitude")

            # Logic: If coordinates still empty AND status is not "Tidak Ditemukan" (0), try "Ambil Lokasi" button
            is_lat_empty = not str(latitude).strip()
            is_long_empty = not str(longitude).strip()
            is_tidak_ditemukan = str(hasil_gc) == "0"
            
            if (is_lat_empty or is_long_empty) and not is_tidak_ditemukan:
                geotag_btn_selector = "button.btn-geotag" # Adjust selector as needed based on actual page
                # Or maybe it has ID or specific text
                # Based on previous knowledge/standard patterns:
                geotag_btn = page.locator("#btn-ambil-lokasi") # Hypothetical selector
                
                # Check actual selector from memory or typical pattern. 
                # Let's try searching for button with text "Ambil Lokasi"
                geotag_locator = page.locator("button", has_text="Ambil Lokasi")
                
                if geotag_locator.count() > 0 and geotag_locator.first.is_visible():
                    log_info("Coordinates empty. Clicking 'Ambil Lokasi'...")
                    monitor.bot_click(geotag_locator.first)
                    # Wait and handle permission prompt handling is done by browser context usually
                    # But we might need to wait for fields to actually fill?
                    time.sleep(2) 

            if status == "gagal" and note == "Hasil GC tidak valid/kosong":
                monitor.bot_goto(TARGET_URL)
                continue

            submit_locator = page.locator("#save-tandai-usaha-btn")
            if submit_locator.count() == 0:
                log_warn(
                    "Tombol submit tidak ditemukan; skipping.",
                    idsbr=idsbr or "-",
                )
                status = "gagal"
                note = "Tombol submit tidak ditemukan"
                monitor.bot_goto(TARGET_URL)
                continue
            if not submit_locator.first.is_visible():
                log_warn(
                    "Tombol submit tidak terlihat; skipping.",
                    idsbr=idsbr or "-",
                )
                status = "gagal"
                note = "Tombol submit tidak terlihat"
                monitor.bot_goto(TARGET_URL)
                continue

            wait_for_block_ui_clear(page, monitor, timeout_s=15)
            # Skip scrolling into view for submit button as it might be in a fixed modal footer
            # try:
            #     submit_locator.first.scroll_into_view_if_needed()
            # except Exception:
            #     pass
            
            # --- START SUBMIT RETRY LOGIC FOR 'SERVER SIBUK' ---
            max_server_busy_retries = 10
            submit_success = False
            
            for attempt in range(max_server_busy_retries + 1):
                try:
                   # HUMANIZATION: Hesitate before submit
                   import random
                   time.sleep(random.uniform(0.5, 1.5))
                   
                   monitor.bot_click(submit_locator.first)
                except Exception as exc:
                    log_warn("Submit click failed", error=str(exc))
                    # Don't abort immediately, check if it was just a glitch or if swal appeared
                
                # Check outcome
                swal_result = None
                confirm_text = "tanpa melakukan geotag"
                success_text = "Data submitted successfully"
                busy_text = "Server Sibuk"
                busy_title = "Server Sibuk"

                def find_any_swal():
                    nonlocal swal_result
                    # Check Busy first
                    # Relax visibility check for 'busy' and 'error' which might be transitioning
                    if page.locator(".swal2-title", has_text=busy_title).count() > 0:
                        swal_result = "busy"
                        return True
                        
                    if page.locator(".swal2-popup", has_text=confirm_text).count() > 0:
                        swal_result = "confirm"
                        return True
                        
                    # Detect error even if animation is running (don't force is_visible)
                    if page.locator(".swal2-icon-error").count() > 0 or \
                       page.locator(".swal2-title", has_text="Error").count() > 0:
                        swal_result = "error"
                        return True
                        
                    if page.locator(".swal2-popup", has_text=success_text).count() > 0 and \
                       page.locator(".swal2-popup").first.is_visible():
                        swal_result = "success"
                        return True
                    return False

                monitor.wait_for_condition(find_any_swal, timeout_s=15)
                
                if swal_result == "busy":
                    log_warn(f"Server Busy detected (Attempt {attempt+1}/{max_server_busy_retries}). Retrying in 3s...")
                    time.sleep(3)
                    
                    # Click 'Coba Lagi' if available, otherwise just retry submit loop
                    retry_btn = page.locator(".swal2-confirm", has_text="Coba Lagi")
                    if retry_btn.count() > 0 and retry_btn.first.is_visible():
                        monitor.bot_click(retry_btn.first)
                        # Waiting for result of 'Coba Lagi' is same as waiting for submit result
                        # So we loop back to check swal again?
                        # Actually 'Coba Lagi' might directly trigger saving. 
                        # Let's wait a bit and check swal again in next iteration of internal loop?
                        # Or simpler: Loop back to clicking submit button? 
                        # Usually 'Coba Lagi' does the submit action. 
                        # But to be safe, if we click Coba Lagi, we should then wait for swal again.
                        
                        # Let's try to just continue the loop effectively acting as re-wait
                        monitor.wait_for_condition(lambda: False, timeout_s=2)
                        continue 
                    else:
                        # Close popup and click submit again
                        close_btn = page.locator(".swal2-cancel", has_text="Tutup")
                        if close_btn.count() > 0:
                            monitor.bot_click(close_btn.first)
                        monitor.wait_for_condition(lambda: False, timeout_s=1)
                        continue

                elif swal_result == "error":
                    log_warn(f"Generic Error popup detected (Attempt {attempt+1}). Attempting aggressive close keys...")
                    time.sleep(1) # Wait slightly for any animation
                    
                    # 1. Try Keyboard Enter (Fastest)
                    try:
                        log_info("Action: Press Enter")
                        page.keyboard.press("Enter")
                        time.sleep(0.5)
                    except Exception as e:
                        log_warn(f"Action Failed (Enter): {e}")

                    # 2. Try JS Click on Confirm Button
                    try:
                        log_info("Action: JS Click .swal2-confirm")
                        page.evaluate("""
                            const btn = document.querySelector('button.swal2-confirm');
                            if(btn) btn.click();
                        """)
                        time.sleep(0.5)
                    except Exception as e:
                        log_warn(f"Action Failed (JS Click): {e}")
                    
                    # 3. Check if still visible, then destroy DOM
                    if page.locator(".swal2-container").count() > 0 and \
                       page.locator(".swal2-container").first.is_visible():
                        log_warn("Swal still visible. ACTION: Destroying via JS.")
                        page.evaluate("""
                            const el = document.querySelector('.swal2-container');
                            if(el) el.remove();
                            // Also remove body classes preventing scroll
                            document.body.classList.remove('swal2-shown', 'swal2-height-auto');
                        """)
                    else:
                        log_info("Swal closed successfully.")
                        
                    # Wait briefly before retrying loop
                    monitor.wait_for_condition(lambda: False, timeout_s=1)
                    continue

                elif swal_result in ["confirm", "success"]:
                     submit_success = True
                     break
                else:
                    # No popup appeared?
                    log_warn("No response popup after submit. Retrying click...")
                    continue
            
            if not submit_success:
                log_error("Failed to submit after multiple retries (Server Busy or No Response).")
                status = "gagal"
                note = "Server Sibuk / No Response"
                monitor.bot_goto(TARGET_URL)
                continue
                
            # --- END SUBMIT RETRY LOGIC ---

            if swal_result == "confirm":
                if not latitude and not longitude:
                    # ... logic for confirm ...
                    confirm_popup = page.locator(".swal2-popup", has_text=confirm_text)
                    confirm_button = confirm_popup.locator(".swal2-confirm", has_text="Ya")
                    if confirm_button.count() > 0:
                        monitor.bot_click(confirm_button.first)
                    else:
                        status = "gagal"; note = "Dialog geotag tanpa tombol Ya"
                        monitor.bot_goto(TARGET_URL); continue
                else:
                    status = "gagal"; note = "Anomali dialog geotag"
                    monitor.bot_goto(TARGET_URL); continue

            # Wait for success if we handled confirm, or if we were already success
            if swal_result != "success":
                # Find success
                def find_success_final():
                    return page.locator(".swal2-popup", has_text=success_text).count() > 0
                if not monitor.wait_for_condition(find_success_final, timeout_s=30): # Increased timeout for final success
                     status = "gagal"; note = "Dialog sukses tidak muncul"
                     monitor.bot_goto(TARGET_URL); continue

            # Handle OK button
            success_popup = page.locator(".swal2-popup", has_text=success_text)
            ok_button = success_popup.locator(".swal2-confirm", has_text="OK")
            if ok_button.count() > 0:
                 monitor.bot_click(ok_button.first)
            
            monitor.wait_for_condition(
                lambda: page.locator(".swal2-popup").count() == 0, timeout_s=10
            )
            monitor.wait_for_condition(
                lambda: is_visible(page, "#search-idsbr") or page.locator(".usaha-card-header").count() > 0,
                timeout_s=10,
            )
            if not page.url.startswith(TARGET_URL):
                monitor.bot_goto(TARGET_URL)
            status = "berhasil"
            note = "Submit sukses"
        except Exception as exc:
            log_error(
                "Error while processing row.",
                idsbr=idsbr or "-",
                error=str(exc),
            )
            status = "error"
            note = str(exc)
        finally:
            run_log_rows.append(
                {
                    "no": excel_row,
                    "idsbr": idsbr or "",
                    "nama_usaha": nama_usaha or "",
                    "alamat": alamat or "",
                    "keberadaanusaha_gc": hasil_gc if hasil_gc is not None else "",
                    "latitude": latitude or "",
                    "longitude": longitude or "",
                    "status": status or "error",
                    "catatan": note,
                }
            )
            # Save log immediately processed row to ensure resume works
            try:
                write_run_log(run_log_rows, run_log_path)
            except Exception as e:
                log_warn(f"Failed to write intermediate log: {e}")

            summary_status = status or "error"
            summary_note = note or "-"
            summary_fields = {
                "row": batch_index,
                "row_excel": excel_row,
                "idsbr": idsbr or "-",
                "status": summary_status,
                "note": summary_note,
            }
            if summary_status == "berhasil":
                log_info("Row summary.", **summary_fields)
            elif summary_status in {"gagal", "skipped"}:
                log_warn("Row summary.", **summary_fields)
            else:
                log_error("Row summary.", **summary_fields)
            
            # --- PERSISTENT STATE SAVING ---
            try:
                state_data = {
                    "last_excel": str(excel_file),
                    "last_row": excel_row,
                    "timestamp": time.time()
                }
                os.makedirs(os.path.dirname(LAST_RUN_STATE_FILE), exist_ok=True)
                with open(LAST_RUN_STATE_FILE, "w") as f:
                    json.dump(state_data, f)
            except Exception:
                pass
            # -------------------------------

            # --- PERSISTENT STATE SAVING ---
            try:
                state_data = {
                    "last_excel": str(excel_file),
                    "last_row": excel_row,
                    "timestamp": time.time()
                }
                os.makedirs(os.path.dirname(LAST_RUN_STATE_FILE), exist_ok=True)
                with open(LAST_RUN_STATE_FILE, "w") as f:
                    json.dump(state_data, f)
                # log_info("State saved.", row=excel_row) # Optional debug
            except Exception as e:
                log_warn("Failed to save state.", error=str(e))
            # -------------------------------

            if progress_callback:
                try:
                    progress_callback(
                        stats["processed"],
                        selected_rows,
                        excel_row,
                    )
                except Exception:
                    pass

            # HUMANIZATION: Random delay after processing row (Success or Error)
            # This does NOT run for rows skipped at the start of the loop.
            import random
            time.sleep(random.uniform(2.0, 4.0))

    log_info("Processing completed.", _spacer=True, _divider=True, **stats)
    write_run_log(run_log_rows, run_log_path)
    log_info("Run log saved.", path=str(run_log_path))
