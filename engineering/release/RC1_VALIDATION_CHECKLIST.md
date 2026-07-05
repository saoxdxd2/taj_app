# Release Candidate 1 (RC1) Validation Checklist

**Target:** TAJ FROID ERP v1.0.0-rc1

This document outlines the mandatory manual validation steps that must be performed by the QA/Release Engineer before certifying RC1 for commercial deployment.

## 1. Installation & Environment Verification
- [ ] **Fresh Install:** Run `TajFroidERP_Setup_v1.0.0-rc1.exe` on a clean Windows machine. Verify installation succeeds without errors.
- [ ] **Shortcuts:** Verify the Desktop shortcut and Start Menu folder are created.
- [ ] **Data Directory:** Navigate to `%LOCALAPPDATA%\TAJ_FROID`. Verify `data`, `logs`, `backups`, and `config` folders are automatically created upon first launch.

## 2. Startup & Database Migration Verification
- [ ] **Cold Boot:** Launch the application. Verify it reaches the Login Screen.
- [ ] **Database Creation:** Verify `%LOCALAPPDATA%\TAJ_FROID\data\taj_froid.db` is created.
- [ ] **Pre-Migration Backup:** Restart the application. Verify a new `.db` file is timestamped and placed in `%LOCALAPPDATA%\TAJ_FROID\backups\`.

## 3. Logging Integrity Verification
- [ ] **Startup Logs:** Open `%LOCALAPPDATA%\TAJ_FROID\logs\app.log`. Verify `Enterprise logging initialized` is present.
- [ ] **Migration Logs:** Check the log for `Executing database migrations...` and `Database migrations completed successfully`.
- [ ] **Exception Capture:** Intentionally cause a UI error (if possible during testing). Verify the traceback is fully recorded in `app.log`.

## 4. Backup & Recovery Verification
- [ ] **Manual Backup:** Go to `Settings -> About Application`. Click "Create Manual Backup". Verify a `.zip` file appears in the `backups/` folder.
- [ ] **Restore Protocol:** Make a distinct change in the application (e.g., create a dummy Customer). Click "Restore Selected Backup" using a backup from *before* the change. Verify the application restarts and the dummy Customer is gone.
- [ ] **Shutdown Backup:** Close the application normally. Verify a `shutdown` prefixed zip file is generated in the `backups/` folder.

## 5. Upgrade & Uninstall Verification
- [ ] **Uninstall Process:** Run the uninstaller from Windows Settings. Verify the `C:\Program Files\TAJ_FROID_ERP` directory is deleted.
- [ ] **Data Preservation:** Verify `%LOCALAPPDATA%\TAJ_FROID` (and all customer data/backups) **SURVIVED** the uninstall process.
- [ ] **Reinstall Upgrade:** Reinstall the application. Verify the application launches and seamlessly connects to the existing database in `%LOCALAPPDATA%` without data loss.

---
**Sign-off:** ___________________________ **Date:** ___________________
