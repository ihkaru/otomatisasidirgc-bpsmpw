# Project Context: Otomatisasi Ground Check Direktori SBR

## Ringkasan Project
Tool otomatisasi berbasis CLI dan GUI untuk melakukan input data Ground Check (GC) Direktori SBR dari file Excel ke sistem web (MatchaPro/DIRGC).

## Tech Stack
- **Language**: Python 3
- **Automation**: Playwright (Stealth Mode Android WebView)
- **GUI**: PyQt5 + PyQt-Fluent-Widgets
- **Data Processing**: Pandas, OpenPyXL

## Struktur Folder
- `dirgc/`: Source code utama (app logic, GUI, browser bot).
- `config/`: Konfigurasi user (credentials.json).
- `data/`: Input file Excel (target data SBR).
- `logs/`: Output logs hasil run.
- `packaging/`: Skript build installer.

## Status Terkini
- Project fully functional.
- Instalasi dependencies selesai (playwright chromium installed).
- Dokumentasi `PANDUAN_OPERASIONAL.md` telah dibuat, mencakup Standard Operating Procedure (SOP) dan Strategi Recovery data.

## History Perubahan
- [2026-01-19] Inisialisasi project.
- [2026-01-19] Pembuatan panduan operasional dan strategi recovery data log.
- [2026-01-20] Menambahkan `CONTRIBUTING.md` dan workflow GitHub Action untuk menolak Pull Request secara otomatis.
- [2026-01-22] SECURITY FIX: Menghapus `config/credentials.json` dari tracking git (namun file tetap ada di lokal). User wajib mengganti password.
