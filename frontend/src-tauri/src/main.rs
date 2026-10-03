#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;

use std::sync::Arc;
use tauri::Manager;

fn main() {
    let backend = Arc::new(backend::Backend::default());
    let managed = backend.clone();
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .manage(backend)
        .setup(move |app| {
            managed.start(app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend::backend_status])
        .build(tauri::generate_context!())
        .expect("could not build Noye desktop")
        .run(|app, event| match event {
            // Closing the only window exits on macOS too, so no invisible
            // backend is left behind. Do not touch Ollama/Docker/Qdrant.
            tauri::RunEvent::WindowEvent {
                event: tauri::WindowEvent::Destroyed,
                ..
            } => app.exit(0),
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
                app.state::<Arc<backend::Backend>>().shutdown()
            }
            _ => {}
        });
}
