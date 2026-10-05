//! Selection lives in the original app-data root, separately from workspace data.
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tauri::Manager;

#[derive(Serialize, Deserialize)]
struct Selection {
    version: u32,
    current: PathBuf,
    previous: PathBuf,
}

#[derive(Serialize)]
pub struct Locations {
    original: PathBuf,
    current: PathBuf,
    previous: Option<PathBuf>,
}

fn read(root: &Path) -> Result<Option<Selection>, String> {
    let path = root.join("workspace-selection.json");
    if !path.exists() {
        return Ok(None);
    }
    let value: Selection = serde_json::from_slice(&fs::read(path).map_err(|e| e.to_string())?)
        .map_err(|_| "Workspace selection is invalid. Reopen the original workspace.")?;
    if value.version != 1 {
        return Err("Unsupported workspace selection. Reopen the original workspace.".into());
    }
    Ok(Some(value))
}

fn validate(root: &Path, selected: &Path) -> Result<PathBuf, String> {
    // The original location is always available for explicit recovery.
    if selected == root {
        return Ok(root.to_owned());
    }
    let canonical = selected
        .canonicalize()
        .map_err(|_| "The selected workspace is missing. Reopen the original workspace.")?;
    if canonical != selected
        || canonical.parent() != root.parent()
        || !canonical
            .file_name()
            .is_some_and(|name| name.to_string_lossy().starts_with("noye-restored-"))
    {
        return Err("Choose a verified backup restored by Noye.".into());
    }
    for name in ["noye-workspace.json", "app.db", "sources", "documents"] {
        let info = fs::symlink_metadata(canonical.join(name))
            .map_err(|_| "The restored workspace is incomplete.")?;
        if info.file_type().is_symlink()
            || (name.ends_with(".json") || name.ends_with(".db")) && !info.is_file()
            || (name == "sources" || name == "documents") && !info.is_dir()
        {
            return Err("The restored workspace contains invalid data paths.".into());
        }
    }
    let receipt: serde_json::Value = serde_json::from_slice(
        &fs::read(canonical.join("noye-workspace.json")).map_err(|e| e.to_string())?,
    )
    .map_err(|_| "The restored workspace receipt is invalid.")?;
    if receipt["format"] != "noye-restored-workspace"
        || receipt["version"] != 1
        || receipt["id"]
            .as_str()
            .and_then(|id| uuid::Uuid::parse_str(id).ok())
            .is_none()
    {
        return Err("The restored workspace receipt is invalid.".into());
    }
    Ok(canonical)
}

pub fn active(root: &Path) -> Result<PathBuf, String> {
    match read(root)? {
        Some(selection) => validate(root, &selection.current),
        None => Ok(root.to_owned()),
    }
}

fn save(root: &Path, destination: &Path) -> Result<(), String> {
    let destination = validate(root, destination)?;
    // Recovery remains possible even if a selected folder was removed.
    let previous = read(root)
        .ok()
        .flatten()
        .map(|s| s.current)
        .unwrap_or(root.to_owned());
    let temporary = root.join(format!(".workspace-selection-{}.tmp", uuid::Uuid::new_v4()));
    let result = (|| {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .map_err(|e| e.to_string())?;
        let selection = Selection {
            version: 1,
            current: destination,
            previous,
        };
        file.write_all(&serde_json::to_vec(&selection).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
        file.sync_all().map_err(|e| e.to_string())?;
        fs::rename(&temporary, root.join("workspace-selection.json")).map_err(|e| e.to_string())?;
        Ok(())
    })();
    let _ = fs::remove_file(temporary);
    result
}

#[tauri::command]
pub fn workspace_locations(app: tauri::AppHandle) -> Result<Locations, String> {
    let root = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let root = root.canonicalize().map_err(|e| e.to_string())?;
    let selection = read(&root)?;
    Ok(Locations {
        current: selection
            .as_ref()
            .map(|s| s.current.clone())
            .unwrap_or(root.clone()),
        previous: selection.map(|s| s.previous),
        original: root,
    })
}

#[tauri::command]
pub async fn select_workspace(
    app: tauri::AppHandle,
    backend: tauri::State<'_, Arc<crate::backend::Backend>>,
    destination: Option<String>,
    confirmed: bool,
) -> Result<(), String> {
    if !confirmed {
        return Err("Save edits and confirm the workspace switch first.".into());
    }
    let root = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let root = root.canonicalize().map_err(|e| e.to_string())?;
    let destination = destination.map(PathBuf::from).unwrap_or(root.clone());
    let backend = backend.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        save(&root, &destination)?;
        // Stop only our backend and its owned services before starting another workspace.
        backend.shutdown();
        Ok::<(), String>(())
    })
    .await
    .map_err(|e| e.to_string())??;
    app.request_restart();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selection_survives_restart_and_original_recovery() {
        let parent = std::env::temp_dir().join(uuid::Uuid::new_v4().to_string());
        fs::create_dir_all(&parent).unwrap();
        let parent = parent.canonicalize().unwrap();
        let root = parent.join("original");
        let restored = parent.join("noye-restored-synthetic");
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(restored.join("sources")).unwrap();
        fs::create_dir_all(restored.join("documents")).unwrap();
        fs::write(restored.join("app.db"), b"synthetic").unwrap();
        fs::write(
            restored.join("noye-workspace.json"),
            serde_json::to_vec(
                &serde_json::json!({"format":"noye-restored-workspace","version":1,
                               "id":uuid::Uuid::new_v4()}),
            )
            .unwrap(),
        )
        .unwrap();
        assert_eq!(active(&root).unwrap(), root);
        save(&root, &restored).unwrap();
        assert_eq!(active(&root).unwrap(), restored);
        fs::remove_dir_all(&restored).unwrap();
        assert!(active(&root).is_err());
        save(&root, &root).unwrap();
        assert_eq!(active(&root).unwrap(), root);
        fs::remove_dir_all(parent).unwrap();
    }

    #[test]
    fn reject_unverified_or_linked_destinations_without_changing_selection() {
        let parent = std::env::temp_dir().join(uuid::Uuid::new_v4().to_string());
        fs::create_dir_all(&parent).unwrap();
        let parent = parent.canonicalize().unwrap();
        let root = parent.join("original");
        let other = parent.join("noye-restored-invalid");
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(&other).unwrap();
        assert!(save(&root, &other).is_err());
        assert!(!root.join("workspace-selection.json").exists());
        #[cfg(unix)]
        {
            let linked = parent.join("noye-restored-link");
            std::os::unix::fs::symlink(&other, &linked).unwrap();
            assert!(save(&root, &linked).is_err());
        }
        fs::remove_dir_all(parent).unwrap();
    }
}
