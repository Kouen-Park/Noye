//! User-requested original links open explicitly in the system browser. The
//! native boundary accepts only source URLs belonging to the current sidecar.
use std::sync::Arc;
use tauri_plugin_shell::ShellExt;

fn allowed_original(base: &str, target: &str) -> bool {
    let Ok(base) = tauri::Url::parse(base) else {
        return false;
    };
    let Ok(url) = tauri::Url::parse(target) else {
        return false;
    };
    if base.scheme() != "http"
        || base.host_str() != Some("127.0.0.1")
        || base.port().is_none()
        || url.origin() != base.origin()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
    {
        return false;
    }
    let Some(mut path) = url.path_segments() else {
        return false;
    };
    if path.next() != Some("files")
        || path
            .next()
            .and_then(|value| uuid::Uuid::parse_str(value).ok())
            .is_none()
        || path.next() != Some("source")
        || path.next().is_some()
    {
        return false;
    }
    url.fragment().is_none_or(|fragment| {
        fragment
            .strip_prefix("page=")
            .and_then(|value| value.parse::<u32>().ok())
            .is_some_and(|page| page > 0)
    })
}

#[tauri::command]
#[allow(deprecated)] // Rust-only Shell::open; no JS shell capability is granted.
pub fn open_original(
    app: tauri::AppHandle,
    backend: tauri::State<'_, Arc<crate::backend::Backend>>,
    url: String,
) -> Result<(), String> {
    let status = crate::backend::backend_status(backend);
    let base = status.url.ok_or("The workspace is not ready. Try again.")?;
    if !allowed_original(&base, &url) {
        return Err("This is not an original from the active workspace.".into());
    }
    app.shell()
        .open(url, None)
        .map_err(|_| "Could not open the original in the system browser.".into())
}

#[cfg(test)]
mod tests {
    use super::allowed_original;
    const ID: &str = "4f6c19d5-62a0-4c30-8c1e-b740508f47eb";

    #[test]
    fn accepts_only_active_workspace_originals_and_real_page_numbers() {
        let base = "http://127.0.0.1:34567";
        let original = format!("{base}/files/{ID}/source");
        assert!(allowed_original(base, &original));
        assert!(allowed_original(base, &format!("{original}#page=3")));
        for target in [
            original.replace("34567", "34568"),
            original.replace("127.0.0.1", "localhost"),
            original.replace(ID, "not-a-source-id"),
            format!("{original}?redirect=https://example.com"),
            format!("{original}/extra"),
            format!("{original}#page=0"),
            format!("{original}#page=1&evil=2"),
            format!("http://user@127.0.0.1:34567/files/{ID}/source"),
            "file:///etc/passwd".into(),
            "https://example.com".into(),
            format!("{base}/services/start"),
        ] {
            assert!(!allowed_original(base, &target), "{target}");
        }
    }
}
