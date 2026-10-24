//! Register the application identity used by GNOME/Wayland's dock.
use std::{fs, path::PathBuf};

pub fn install() -> Result<(), String> {
    let data = std::env::var_os("XDG_DATA_HOME").map(PathBuf::from).filter(|p| p.is_absolute())
        .or_else(|| std::env::var_os("HOME").map(|p| PathBuf::from(p).join(".local/share")))
        .ok_or("Cannot locate user application directory")?;
    let icons = data.join("icons/hicolor/256x256/apps");
    let applications = data.join("applications");
    fs::create_dir_all(&icons).and_then(|_|fs::create_dir_all(&applications)).map_err(|e|e.to_string())?;
    let icon = icons.join("studio.clash.desktop.png");
    let bytes = include_bytes!("../icons/icon.png");
    if fs::read(&icon).ok().as_deref() != Some(bytes.as_slice()) { fs::write(&icon,bytes).map_err(|e|e.to_string())?; }
    let content = super::linux_autostart::entry(&std::env::current_exe().map_err(|e|e.to_string())?,&super::paths::data_dir())?
        .replace(" --background\n","\n").replace("X-GNOME-Autostart-enabled=true\n","")
        + "Icon=studio.clash.desktop\nStartupWMClass=studio.clash.desktop\nCategories=Network;\nStartupNotify=true\n";
    let path = applications.join("studio.clash.desktop.desktop");
    if fs::read_to_string(&path).ok().as_deref() != Some(content.as_str()) {
        let temporary=path.with_extension("tmp");
        fs::write(&temporary,content).and_then(|_|fs::rename(temporary,path)).map_err(|e|e.to_string())?;
        let _=std::process::Command::new("update-desktop-database").arg(&applications).output();
    }
    Ok(())
}
