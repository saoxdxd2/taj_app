# Production Readiness — TAJ FROID Mobile Sync

## Pre-flight checklist (avoid production problems)

### Data safety
- [ ] One-time migration: push existing desktop SQLite DB up to Turso before enabling sync on multiple devices.
- [ ] Backup before first sync (BackupManager.create_backup already does this on app close).
- [ ] Per-field versioning on shared entities (add `version`, `updated_at`, `updated_by` columns) before bidirectional edits.
- [ ] Conflict UI: show diffs and let operator choose; never silently overwrite.
- [ ] Rollback plan: restore from backup if sync corrupts data.

### Auth & secrets
- [ ] Agent token bootstrapped via ERP_SETUP_SECRET env var; stored in keyring; never in DB/logs.
- [ ] Device tokens hashed (sha256) on relay; revocable from desktop.
- [ ] X25519 private key in Windows Credential Manager; documented backup step (key loss = unrecoverable scans).
- [ ] No secrets in PWA bundle, logs, or database.

### Offline & sync
- [ ] IndexedDB persistence on phone (survives refresh; cleared only by user).
- [ ] Offline queue with client UUID idempotency (no duplicate uploads).
- [ ] Retry with exponential backoff; never drop queued scans.
- [ ] Status cursor persisted; phone shows En attente / Envoyé / À vérifier / Importé / Refusé.
- [ ] Desktop tray service runs agent even when ERP closed; shares DB safely (WAL + busy_timeout).
- [ ] Relay downtime handled gracefully (queue, retry, no data loss).

### Android APK
- [ ] Bubblewrap TWA built from deployed PWA (mobile.tajfroid.com must be live + HTTPS).
- [ ] Digital Asset Links (assetlinks.json) on the domain to verify app ownership.
- [ ] Sideload via USB/QR; no Play Store needed.
- [ ] Test on real device: airplane-mode capture, reconnect upload, status polling.

### Desktop
- [ ] Mobile nav entry + settings UI (relay URL, bootstrap, pairing QR) — done.
- [ ] Tray service autostart (Task Scheduler entry) — optional.
- [ ] Stop agent on app close; avoid double agent (tray + ERP).

### Monitoring
- [ ] Relay health endpoint (/api/health) polled by desktop.
- [ ] Logs redacted (no tokens, no file contents).
- [ ] Retention: delete blob + row 30 days after terminal status.

### Testing before production
- [ ] Unit tests with httpx.MockTransport for agent.
- [ ] Real-phone test: airplane-mode capture, reconnect, desktop OCR, DRAFT purchase, phone shows reference.
- [ ] Relay DB + Blob contain only ciphertext (verify).
- [ ] tajfroid.com unchanged (verify).