//! Relaunch a packaged macOS app through Launch Services after singleton cleanup.
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::Manager;

#[derive(Default)]
pub struct Relaunch(AtomicBool);

fn bundle_path(executable: &Path) -> Option<PathBuf> {
    let macos = executable.parent()?;
    let contents = macos.parent()?;
    let bundle = contents.parent()?;
    (macos.file_name()? == "MacOS"
        && contents.file_name()? == "Contents"
        && bundle.extension()? == "app")
        .then(|| bundle.to_owned())
}

pub fn request(app: &tauri::AppHandle) {
    if std::env::current_exe()
        .ok()
        .and_then(|path| bundle_path(&path))
        .is_some()
    {
        app.state::<Relaunch>().0.store(true, Ordering::Relaxed);
        app.exit(0);
    } else {
        // Development executables are not application bundles.
        app.request_restart();
    }
}

pub fn after_exit(app: &tauri::AppHandle) {
    if !app.state::<Relaunch>().0.swap(false, Ordering::Relaxed) {
        return;
    }
    // Tauri delivers plugin Exit handlers before the application callback, so
    // the single-instance socket is already released. Launch only our own
    // bundle, never a destination supplied by a workspace or UI argument.
    let launched = std::env::current_exe()
        .ok()
        .and_then(|path| bundle_path(&path))
        .and_then(|bundle| {
            std::process::Command::new("/usr/bin/open")
                .arg("-n")
                .arg(bundle)
                .status()
                .ok()
        })
        .is_some_and(|status| status.success());
    if !launched {
        eprintln!("macOS could not relaunch the bundle; using the framework restart.");
        tauri::process::restart(&app.env());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relaunch_only_derives_the_executables_own_application_bundle() {
        assert_eq!(
            bundle_path(Path::new(
                "/Applications/Noye QA.app/Contents/MacOS/noye-desktop"
            )),
            Some(PathBuf::from("/Applications/Noye QA.app"))
        );
        for path in [
            "/tmp/target/debug/noye-desktop",
            "/tmp/workspace/Contents/MacOS/noye-desktop",
            "/tmp/Noye.app/Other/MacOS/noye-desktop",
            "/tmp/Noye.app/Contents/Other/noye-desktop",
        ] {
            assert_eq!(bundle_path(Path::new(path)), None);
        }
    }
}
