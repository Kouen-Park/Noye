//! Export destinations come only from the OS save dialog, never JavaScript paths.
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

#[derive(Default)]
pub struct Exports(AtomicBool);

struct ExportGuard<'a>(&'a AtomicBool);
impl Drop for ExportGuard<'_> {
    fn drop(&mut self) {
        self.0.store(false, Ordering::Release);
    }
}

impl Exports {
    fn begin(&self) -> Result<ExportGuard<'_>, String> {
        self.0
            .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
            .map_err(|_| "Finish or cancel the current export first.")?;
        Ok(ExportGuard(&self.0))
    }
}

fn markdown_filename(title: &str) -> String {
    let cleaned: String = title
        .chars()
        .filter(|c| !c.is_control() && !matches!(c, '/' | '\\' | ':'))
        .take(120)
        .collect();
    let name = cleaned.trim();
    format!("{}.md", if name.is_empty() { "document" } else { name })
}

fn choose_save(filename: &str) -> Result<Option<PathBuf>, String> {
    #[cfg(target_os = "macos")]
    {
        use objc2::MainThreadMarker;
        use objc2_app_kit::{NSModalResponseOK, NSSavePanel};
        use objc2_foundation::NSString;
        let marker = MainThreadMarker::new().ok_or("Save dialog needs the main thread")?;
        let panel = NSSavePanel::savePanel(marker);
        panel.setNameFieldStringValue(&NSString::from_str(filename));
        panel.setCanCreateDirectories(true);
        panel.setMessage(Some(&NSString::from_str(
            "Choose a new filename. Existing files are preserved.",
        )));
        if panel.runModal() != NSModalResponseOK {
            return Ok(None);
        }
        let path = panel
            .URL()
            .and_then(|url| url.path())
            .ok_or("No file selected")?;
        Ok(Some(PathBuf::from(path.to_string())))
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = filename;
        Err("Native exports currently target macOS.".into())
    }
}

async fn destination(app: tauri::AppHandle, filename: String) -> Result<Option<PathBuf>, String> {
    let (sender, receiver) = std::sync::mpsc::sync_channel(1);
    app.run_on_main_thread(move || {
        let _ = sender.send(choose_save(&filename));
    })
    .map_err(|_| "Could not open the native save dialog")?;
    tauri::async_runtime::spawn_blocking(move || receiver.recv())
        .await
        .map_err(|e| e.to_string())?
        .map_err(|_| "The save dialog was closed")?
}

fn write_markdown(path: &Path, content: &str) -> std::io::Result<()> {
    use std::io::Write;
    struct Staged(PathBuf);
    impl Drop for Staged {
        fn drop(&mut self) {
            let _ = std::fs::remove_file(&self.0);
        }
    }
    let temporary = path
        .parent()
        .ok_or(std::io::ErrorKind::InvalidInput)?
        .join(format!(".noye-export-{}", uuid::Uuid::new_v4()));
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)?;
    let staged = Staged(temporary);
    file.write_all(content.as_bytes())?;
    file.sync_all()?;
    #[cfg(target_os = "macos")]
    {
        use std::ffi::CString;
        use std::os::unix::ffi::OsStrExt;
        unsafe extern "C" {
            fn renamex_np(
                from: *const std::ffi::c_char,
                to: *const std::ffi::c_char,
                flags: u32,
            ) -> i32;
        }
        let from = CString::new(staged.0.as_os_str().as_bytes())?;
        let to = CString::new(path.as_os_str().as_bytes())?;
        // Public macOS no-replacement rename. Unlike hard links, this also
        // supports removable volumes that cannot create file hard links.
        if unsafe {
            renamex_np(from.as_ptr(), to.as_ptr(), 4 /* RENAME_EXCL */)
        } != 0
        {
            return Err(std::io::Error::last_os_error());
        }
    }
    #[cfg(not(target_os = "macos"))]
    std::fs::hard_link(&staged.0, path)?;
    Ok(())
}

#[tauri::command]
pub async fn save_markdown(
    app: tauri::AppHandle,
    exports: tauri::State<'_, Exports>,
    title: String,
    content: String,
) -> Result<bool, String> {
    let _guard = exports.begin()?;
    let Some(path) = destination(app, markdown_filename(&title)).await? else {
        return Ok(false);
    };
    tauri::async_runtime::spawn_blocking(move || write_markdown(&path, &content))
        .await
        .map_err(|e| e.to_string())?
        .map_err(|_| {
            "Could not save Markdown. Choose a new filename and check folder permissions."
        })?;
    Ok(true)
}

#[tauri::command]
pub async fn save_workspace_backup(
    app: tauri::AppHandle,
    exports: tauri::State<'_, Exports>,
    backend: tauri::State<'_, Arc<crate::backend::Backend>>,
) -> Result<bool, String> {
    let _guard = exports.begin()?;
    let Some(path) = destination(app, "noye-workspace.noye.zip".into()).await? else {
        return Ok(false);
    };
    let backend = backend.inner().clone();
    tauri::async_runtime::spawn_blocking(move || backend.export_backup(&path.to_string_lossy()))
        .await
        .map_err(|e| e.to_string())??;
    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;
    struct TestDirectory(PathBuf);
    impl Drop for TestDirectory {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
    fn directory() -> TestDirectory {
        let path = std::env::temp_dir().join(format!("noye-export-test-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&path).unwrap();
        TestDirectory(path)
    }
    #[test]
    fn writes_exact_utf8_without_overwriting_existing_content() {
        let root = directory();
        let file = root.0.join("saved.md");
        let text = "<!-- comment -->\n한국어 -- \"quoted\" `->`\n";
        write_markdown(&file, text).unwrap();
        assert_eq!(std::fs::read(&file).unwrap(), text.as_bytes());
        assert_eq!(
            write_markdown(&file, "replacement").unwrap_err().kind(),
            std::io::ErrorKind::AlreadyExists
        );
        assert_eq!(std::fs::read_to_string(&file).unwrap(), text);
        assert_eq!(std::fs::read_dir(&root.0).unwrap().count(), 1);
    }
    #[test]
    #[cfg(unix)]
    fn never_follows_a_destination_symlink() {
        let root = directory();
        let original = root.0.join("original.md");
        std::fs::write(&original, "preserved").unwrap();
        let link = root.0.join("link.md");
        std::os::unix::fs::symlink(&original, &link).unwrap();
        assert!(write_markdown(&link, "replacement").is_err());
        assert_eq!(std::fs::read_to_string(original).unwrap(), "preserved");
        assert_eq!(std::fs::read_dir(&root.0).unwrap().count(), 2);
    }
    #[test]
    fn only_one_native_export_can_be_open() {
        let exports = Exports::default();
        let guard = exports.begin().unwrap();
        assert!(exports.begin().is_err());
        drop(guard);
        assert!(exports.begin().is_ok());
    }
    #[test]
    fn suggestions_cannot_supply_destination_directories() {
        assert_eq!(markdown_filename("한국어 / notes: "), "한국어  notes.md");
        assert_eq!(markdown_filename("/\\:\n"), "document.md");
        assert!(!markdown_filename("../nested/../../name").contains('/'));
    }
}
