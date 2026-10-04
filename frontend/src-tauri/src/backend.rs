use serde::Serialize;
use std::sync::{Arc, Condvar, Mutex};
use std::time::Duration;
use tauri::Manager;
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

#[derive(Clone, Serialize)]
pub struct BackendStatus {
    state: &'static str,
    url: Option<String>,
    error: Option<String>,
}

struct Process {
    child: Option<CommandChild>,
    exited: bool,
    status: BackendStatus,
    configured: u64,
    next_config: u64,
}

pub struct Backend {
    process: Mutex<Process>,
    exit: Condvar,
}

impl Default for Backend {
    fn default() -> Self {
        Self {
            process: Mutex::new(Process {
                child: None,
                exited: false,
                status: BackendStatus {
                    state: "starting",
                    url: None,
                    error: None,
                },
                configured: 0,
                next_config: 2,
            }),
            exit: Condvar::new(),
        }
    }
}

fn ready_url(line: &[u8]) -> Option<String> {
    let value: serde_json::Value = serde_json::from_slice(line).ok()?;
    if value["event"] != "ready" {
        return None;
    }
    let url = value["url"].as_str()?;
    let port = url.strip_prefix("http://127.0.0.1:")?.parse::<u16>().ok()?;
    (port != 0).then(|| url.to_owned())
}

impl Backend {
    pub fn start(self: &Arc<Self>, app: &tauri::AppHandle) {
        let spawned = (|| {
            let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
            std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
            app.shell().sidecar("noye-backend").map_err(|e| e.to_string())?
                .args(["--data-dir".to_owned(), dir.to_string_lossy().into_owned()])
                .env("FRONTEND_ORIGINS", "tauri://localhost,http://tauri.localhost,http://localhost:3000,http://127.0.0.1:3000")
                .env("NOYE_CONTROL_TOKEN", &app.state::<Arc<crate::preferences::PreferenceStore>>().token)
                .spawn().map_err(|e| e.to_string())
        })();
        match spawned {
            Ok((mut events, child)) => {
                self.process.lock().unwrap().child = Some(child);
                let store = app.state::<Arc<crate::preferences::PreferenceStore>>();
                let config = store.configuration().unwrap_or_else(|_| {
                    eprintln!("Keychain unavailable; cloud generation is disabled until AI settings are saved.");
                    store.local_configuration().unwrap()
                });
                let frame = serde_json::json!({"event":"configure", "id":1, "values":config});
                let _ = self
                    .process
                    .lock()
                    .unwrap()
                    .child
                    .as_mut()
                    .unwrap()
                    .write(format!("{frame}\n").as_bytes());
                let backend = self.clone();
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = events.recv().await {
                        match event {
                            CommandEvent::Stdout(line) => {
                                if let Ok(value) =
                                    serde_json::from_slice::<serde_json::Value>(&line)
                                {
                                    if value["event"] == "configured" {
                                        backend.process.lock().unwrap().configured =
                                            value["id"].as_u64().unwrap_or(0);
                                        let mut process = backend.process.lock().unwrap();
                                        if process.status.url.is_some() {
                                            process.status.state = "ready";
                                        }
                                        drop(process);
                                        backend.exit.notify_all();
                                    }
                                }
                                if let Some(url) = ready_url(&line) {
                                    let mut process = backend.process.lock().unwrap();
                                    process.status = BackendStatus {
                                        state: if process.configured > 0 {
                                            "ready"
                                        } else {
                                            "starting"
                                        },
                                        url: Some(url),
                                        error: None,
                                    };
                                }
                            }
                            CommandEvent::Stderr(line) => {
                                eprintln!("{}", String::from_utf8_lossy(&line))
                            }
                            CommandEvent::Terminated(_) => break,
                            _ => {}
                        }
                    }
                    let mut process = backend.process.lock().unwrap();
                    process.exited = true;
                    process.status = BackendStatus {
                        state: "failed",
                        url: None,
                        error: Some("The local backend stopped. Quit Noye and reopen it.".into()),
                    };
                    backend.exit.notify_all();
                });
            }
            Err(reason) => {
                eprintln!("Backend launch failed: {reason}");
                let mut process = self.process.lock().unwrap();
                process.exited = true;
                process.status = BackendStatus {
                    state: "failed",
                    url: None,
                    error: Some(
                        "Noye could not launch its bundled backend. Check the app-data logs."
                            .into(),
                    ),
                };
            }
        }
    }

    pub fn configure(&self, values: serde_json::Value) -> Result<(), String> {
        let mut process = self.process.lock().unwrap();
        let id = process.next_config;
        process.next_config += 1;
        let frame = serde_json::json!({"event":"configure", "id":id, "values":values});
        process
            .child
            .as_mut()
            .ok_or("Backend unavailable")?
            .write(format!("{frame}\n").as_bytes())
            .map_err(|_| "Backend unavailable")?;
        let (process, _) = self
            .exit
            .wait_timeout_while(process, Duration::from_secs(5), |state| {
                !state.exited && state.configured < id
            })
            .unwrap();
        if process.configured >= id {
            Ok(())
        } else {
            Err("Backend did not confirm settings".into())
        }
    }

    pub fn shutdown(&self) {
        let mut process = self.process.lock().unwrap();
        if let Some(child) = process.child.as_mut() {
            let _ = child.write(b"shutdown\n");
        }
        let (mut process, _) = self
            .exit
            .wait_timeout_while(process, Duration::from_secs(8), |process| !process.exited)
            .unwrap();
        if let Some(child) = process.child.take() {
            if !process.exited {
                let _ = child.kill();
            }
        }
        process.exited = true;
    }
}

#[tauri::command]
pub fn backend_status(backend: tauri::State<'_, Arc<Backend>>) -> BackendStatus {
    backend.process.lock().unwrap().status.clone()
}

#[cfg(test)]
mod tests {
    use super::ready_url;

    #[test]
    fn only_accepts_our_loopback_readiness_protocol() {
        assert_eq!(
            ready_url(br#"{"event":"ready","url":"http://127.0.0.1:12345"}"#),
            Some("http://127.0.0.1:12345".into())
        );
        for line in [
            br#"{"event":"ready","url":"https://example.com:8000"}"#.as_slice(),
            br#"{"event":"ready","url":"http://127.0.0.1:0"}"#,
            br#"{"event":"ready","url":"http://127.0.0.1:8000/evil"}"#,
            br#"{"event":"ready","url":"http://127.0.0.1:999999"}"#,
            br#"{"event":"other","url":"http://127.0.0.1:8000"}"#,
            b"not JSON",
        ] {
            assert_eq!(ready_url(line), None);
        }
    }
}
