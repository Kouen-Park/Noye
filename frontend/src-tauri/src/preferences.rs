//! Keys live only in macOS Keychain and the private parent-to-sidecar pipe.
use crate::backend::Backend;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use tauri::Manager;

const PROVIDERS: [&str; 3] = ["openai", "anthropic", "gemini"];
const SERVICE: &str = "app.noye.desktop.ai";

#[derive(Clone, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Preferences {
    pub provider: String,
    pub ollama_model: String,
    pub openai_model: String,
    pub anthropic_model: String,
    pub gemini_model: String,
}

impl Default for Preferences {
    fn default() -> Self {
        Self {
            provider: "ollama".into(),
            ollama_model: "qwen3.5:4b".into(),
            openai_model: "gpt-4.1-mini".into(),
            anthropic_model: "claude-haiku-4-5".into(),
            gemini_model: "gemini-3.8-flash".into(),
        }
    }
}

impl Preferences {
    fn validate(&self) -> Result<(), String> {
        if self.provider != "ollama" && !PROVIDERS.contains(&self.provider.as_str()) {
            return Err("Choose a supported provider.".into());
        }
        for (name, local) in [
            (&self.ollama_model, true),
            (&self.openai_model, false),
            (&self.anthropic_model, false),
            (&self.gemini_model, false),
        ] {
            if name.is_empty()
                || name.len() > 200
                || !name.bytes().all(|c| {
                    c.is_ascii_alphanumeric()
                        || b"._-".contains(&c)
                        || (local && b":/".contains(&c))
                })
            {
                return Err("Enter valid model identifiers, not URLs.".into());
            }
        }
        Ok(())
    }
}

pub struct PreferenceStore {
    path: PathBuf,
    values: Mutex<Preferences>,
    operation: Mutex<()>,
    pub token: String,
}

fn key(provider: &str) -> Result<keyring::Entry, String> {
    if !PROVIDERS.contains(&provider) {
        return Err("Unsupported cloud provider.".into());
    }
    keyring::Entry::new(SERVICE, provider).map_err(|_| "Could not access macOS Keychain.".into())
}

fn read_key(provider: &str) -> Result<String, String> {
    match key(provider)?.get_password() {
        Ok(value) => Ok(value),
        Err(keyring::Error::NoEntry) => Ok(String::new()),
        Err(_) => Err("Could not read macOS Keychain. Allow Noye access and try again.".into()),
    }
}

impl PreferenceStore {
    pub fn new(app: &tauri::AppHandle) -> Result<Self, String> {
        let path = app
            .path()
            .app_data_dir()
            .map_err(|_| "App-data folder is unavailable.")?
            .join("ai-settings.json");
        let values = if path.exists() {
            let bytes = std::fs::read(&path).map_err(|_| "Could not read AI settings.")?;
            serde_json::from_slice::<Preferences>(&bytes)
                .map_err(|_| "AI settings are invalid; preserve the file and repair it.")?
        } else {
            Preferences::default()
        };
        values.validate()?;
        Ok(Self {
            path,
            values: Mutex::new(values),
            operation: Mutex::new(()),
            token: uuid::Uuid::new_v4().to_string(),
        })
    }

    pub fn configuration(&self) -> Result<Value, String> {
        let mut config = self.local_configuration()?;
        for provider in PROVIDERS {
            config[format!("{provider}_api_key")] = json!(read_key(provider)?);
        }
        Ok(config)
    }

    pub fn local_configuration(&self) -> Result<Value, String> {
        let values = self.values.lock().unwrap().clone();
        let mut config =
            serde_json::to_value(values).map_err(|_| "Could not prepare AI settings.")?;
        config.as_object_mut().unwrap().remove("provider");
        for provider in PROVIDERS {
            config[format!("{provider}_api_key")] = json!("");
        }
        Ok(config)
    }
}

#[tauri::command]
pub async fn ai_settings(app: tauri::AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let store = app.state::<Arc<PreferenceStore>>();
        let mut result = serde_json::to_value(store.values.lock().unwrap().clone())
            .map_err(|_| "Could not read settings.")?;
        for provider in PROVIDERS {
            result[format!("{provider}_configured")] = json!(!read_key(provider)?.is_empty());
        }
        result["control_token"] = json!(store.token);
        // A suggestion only: the user must confirm Ollama's actual storage volume.
        result["storage_path"] = json!(app
            .path()
            .home_dir()
            .map_err(|_| "Home folder unavailable.")?
            .to_string_lossy());
        Ok(result)
    })
    .await
    .map_err(|_| "Could not read AI settings.".to_owned())?
}

#[tauri::command]
pub async fn save_ai_settings(
    app: tauri::AppHandle,
    values: Preferences,
    credential_provider: Option<String>,
    credential: Option<String>,
    remove_key: bool,
) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        values.validate()?;
        let store = app.state::<Arc<PreferenceStore>>();
        let _operation = store.operation.lock().unwrap();
        let mut current = store.values.lock().unwrap();
        if let Some(provider) = credential_provider {
            let entry = key(&provider)?;
            if remove_key {
                match entry.delete_credential() {
                    Ok(()) | Err(keyring::Error::NoEntry) => {},
                    Err(_) => return Err("Could not remove the key from macOS Keychain.".into()),
                }
            } else if let Some(secret) = credential {
                let secret = secret.trim();
                if secret.is_empty() || secret.len() > 4096 || secret.chars().any(char::is_control) {
                    return Err("Enter a non-empty API key without control characters.".into());
                }
                entry.set_password(secret).map_err(|_| "Could not save the key in macOS Keychain. Nothing is stored in plaintext.")?;
            }
        }
        let bytes = serde_json::to_vec_pretty(&values).map_err(|_| "Could not save model preferences.")?;
        let temporary = store.path.with_extension("json.tmp");
        std::fs::write(&temporary, bytes).map_err(|_| "Could not save model preferences. Keychain may already be updated.")?;
        std::fs::rename(&temporary, &store.path).map_err(|_| "Could not save model preferences. Keychain may already be updated.")?;
        *current = values;
        drop(current);
        let config = store.configuration()?;
        app.state::<Arc<Backend>>().configure(config)
            .map_err(|_| "Settings were saved, but the backend did not confirm them. Quit and reopen Noye before using AI.".to_owned())
    }).await.map_err(|_| "Could not save AI settings.".to_owned())?
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn validates_known_providers_and_identifiers_only() {
        let mut values = Preferences::default();
        assert!(values.validate().is_ok());
        values.provider = "unknown".into();
        assert!(values.validate().is_err());
        values.provider = "openai".into();
        values.openai_model = "https://evil.com".into();
        assert!(values.validate().is_err());
    }
    #[test]
    fn preference_file_has_no_credentials() {
        let json = serde_json::to_string(&Preferences::default()).unwrap();
        assert!(!json.contains("key"));
        assert!(serde_json::from_str::<Preferences>(r#"{"openai_api_key":"secret"}"#).is_err());
    }
}
