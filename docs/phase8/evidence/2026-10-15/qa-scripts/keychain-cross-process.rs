// Opt-in QA with one synthetic value in a fresh, disposable service namespace.
// This checks the platform keyring across processes, not packaged-app UI access.
use std::process::Command;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    if let Some(service) = std::env::args().nth(1) {
        if !service.starts_with("com.noye.phase8-keychain-qa.") {
            return Err("Only the QA namespace is allowed".into());
        }
        let entry = keyring::Entry::new(&service, "synthetic-provider")?;
        let expected = std::env::var("NOYE_QA_SYNTHETIC_VALUE")?;
        if entry.get_password()? != expected {
            return Err("Synthetic value did not survive the process boundary".into());
        }
        println!("cross_process_read=true");
        return Ok(());
    }
    let service = format!("com.noye.phase8-keychain-qa.{}", uuid::Uuid::new_v4());
    let value = format!("synthetic-test-value-{}", uuid::Uuid::new_v4());
    let entry = keyring::Entry::new(&service, "synthetic-provider")?;
    entry.set_password(&value)?;
    let child = Command::new(std::env::current_exe()?)
        .arg(&service)
        .env("NOYE_QA_SYNTHETIC_VALUE", &value)
        .output();
    // Clean up only this program's newly created item, including failed checks.
    let cleanup = entry.delete_credential();
    let child = child?;
    cleanup?;
    if !child.status.success() {
        return Err("Synthetic child-process check failed".into());
    }
    if !matches!(entry.get_password(), Err(keyring::Error::NoEntry)) {
        return Err("Disposable QA item was not removed".into());
    }
    println!("service={service}");
    print!("{}", String::from_utf8(child.stdout)?);
    println!("qa_item_removed=true");
    Ok(())
}
