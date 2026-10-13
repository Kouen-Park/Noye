#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod exports;
mod folders;
mod menu;
mod originals;
mod preferences;
#[cfg(target_os = "macos")]
mod relaunch;
mod workspaces;

use std::sync::Arc;
use tauri::Manager;

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn main() {
    let backend = Arc::new(backend::Backend::default());
    let managed = backend.clone();
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            show_main_window(app);
        }))
        .plugin(tauri_plugin_shell::init())
        .manage(backend)
        .manage(exports::Exports::default())
        .setup(move |app| {
            menu::install(app.handle())?;
            #[cfg(target_os = "macos")]
            app.manage(relaunch::Relaunch::default());
            app.manage(Arc::new(preferences::PreferenceStore::new(app.handle())?));
            managed.start(app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            backend::backend_status,
            preferences::ai_settings,
            preferences::save_ai_settings,
            workspaces::workspace_locations,
            workspaces::select_workspace,
            folders::choose_source_folder,
            folders::reveal_source_folder,
            originals::open_original,
            exports::save_markdown,
            exports::save_workspace_backup
        ])
        .build(tauri::generate_context!())
        .expect("could not build Noye desktop")
        .run(|app, event| match event {
            // Explicit launches and Dock reopen actions should show the workspace.
            tauri::RunEvent::Ready => show_main_window(app),
            #[cfg(target_os = "macos")]
            tauri::RunEvent::Reopen { .. } => show_main_window(app),
            // Closing the only window exits on macOS too, so no invisible
            // backend is left behind. Its shutdown only stops service handles
            // started by this session, never external Ollama/Docker/Qdrant.
            tauri::RunEvent::WindowEvent {
                event: tauri::WindowEvent::Destroyed,
                ..
            } => app.exit(0),
            tauri::RunEvent::ExitRequested { .. } => {
                app.state::<Arc<backend::Backend>>().shutdown()
            }
            tauri::RunEvent::Exit => {
                app.state::<Arc<backend::Backend>>().shutdown();
                #[cfg(target_os = "macos")]
                relaunch::after_exit(app);
            }
            _ => {}
        });
}
