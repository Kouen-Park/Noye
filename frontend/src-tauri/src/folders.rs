//! Paths enter the application only through the system folder picker.
use serde_json::json;
use std::process::Command;
use std::sync::Arc;

fn choose_folder() -> Result<Option<String>, String> {
    #[cfg(target_os = "macos")]
    {
        use objc2::MainThreadMarker;
        use objc2_app_kit::{NSModalResponseOK, NSOpenPanel};
        use objc2_foundation::NSString;
        let marker = MainThreadMarker::new().ok_or("Folder picker needs the main thread")?;
        let panel = NSOpenPanel::openPanel(marker);
        panel.setCanChooseDirectories(true);
        panel.setCanChooseFiles(false);
        panel.setAllowsMultipleSelection(false);
        panel.setCanCreateDirectories(true);
        panel.setMessage(Some(&NSString::from_str("Choose a Noye knowledge folder")));
        if panel.runModal() != NSModalResponseOK {
            return Ok(None);
        }
        let selected = panel
            .URL()
            .and_then(|url| url.path())
            .ok_or("No folder selected")?;
        let canonical = std::path::Path::new(&selected.to_string())
            .canonicalize()
            .map_err(|_| "The selected folder is unavailable")?;
        Ok(Some(canonical.to_string_lossy().into_owned()))
    }
    #[cfg(not(target_os = "macos"))]
    Err("Native folder selection currently targets macOS.".into())
}

#[tauri::command]
pub async fn choose_source_folder(
    app: tauri::AppHandle,
    backend: tauri::State<'_, Arc<crate::backend::Backend>>,
    kind: String,
    root_id: Option<String>,
) -> Result<Option<String>, String> {
    if kind != "managed" && kind != "connected" {
        return Err("Unknown folder kind".into());
    }
    let (sender, receiver) = std::sync::mpsc::sync_channel(1);
    app.run_on_main_thread(move || {
        let _ = sender.send(choose_folder());
    })
    .map_err(|_| "Could not open the native folder picker")?;
    let selected = tauri::async_runtime::spawn_blocking(move || receiver.recv())
        .await
        .map_err(|e| e.to_string())?
        .map_err(|_| "The folder picker was closed")??;
    let backend = backend.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let Some(path) = selected else {
            return Ok(None);
        };
        backend
            .folder_request(
                "register_root",
                json!({"path":path,"kind":kind,"root_id":root_id}),
            )
            .map(Some)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn reveal_source_folder(
    backend: tauri::State<'_, Arc<crate::backend::Backend>>,
    root_id: Option<String>,
    source_id: Option<String>,
) -> Result<(), String> {
    if root_id.is_some() == source_id.is_some() {
        return Err("Choose one registered folder or source".into());
    }
    let backend = backend.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let (action, values) = if let Some(id) = root_id {
            ("reveal_root", json!({"root_id":id}))
        } else {
            ("reveal_source", json!({"source_id":source_id.unwrap()}))
        };
        let path = backend.folder_request(action, values)?;
        let mut command = Command::new("/usr/bin/open");
        if action == "reveal_source" {
            command.arg("-R");
        }
        let status = command
            .arg(path)
            .status()
            .map_err(|_| "Finder could not open this original")?;
        if status.success() {
            Ok(())
        } else {
            Err("Finder could not open this original".into())
        }
    })
    .await
    .map_err(|e| e.to_string())?
}
