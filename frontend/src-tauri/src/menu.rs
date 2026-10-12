//! Preserve standard native editing/window menus while adding workspace actions.
use tauri::{
    menu::{Menu, MenuItemBuilder, MenuItemKind},
    Emitter, Manager,
};

pub fn install(app: &tauri::AppHandle) -> tauri::Result<()> {
    let menu = Menu::default(app)?;
    let settings = MenuItemBuilder::with_id("settings", "Settings…")
        .accelerator("CmdOrCtrl+,")
        .build(app)?;
    let setup = MenuItemBuilder::with_id("setup", "AI Setup…").build(app)?;
    let sidebar = MenuItemBuilder::with_id("sidebar", "Toggle Sidebar")
        .accelerator("CmdOrCtrl+Shift+L")
        .build(app)?;
    let items = menu.items()?;
    if let Some(MenuItemKind::Submenu(application)) = items.first() {
        application.insert(&settings, 2)?;
        application.insert(&setup, 3)?;
    }
    for item in items {
        if let MenuItemKind::Submenu(submenu) = item {
            if submenu.text()? == "View" {
                submenu.append(&sidebar)?;
            }
        }
    }
    app.set_menu(menu)?;
    app.on_menu_event(|app, event| {
        let id = event.id().as_ref();
        if matches!(id, "settings" | "setup" | "sidebar") {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.emit("noye-menu-action", id);
            }
        }
    });
    Ok(())
}
