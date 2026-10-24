//! XDG desktop-session autostart for the current user, without root.
use std::{fs, path::{Path, PathBuf}};

fn exec_argument(value: &str) -> Result<String, String> {
    if value.chars().any(char::is_control) { return Err("Autostart path contains control characters".into()); }
    // Exec quoting followed by Desktop Entry string escaping. Percent is a field code.
    let mut quoted = String::from("\"");
    for ch in value.chars() {
        match ch {
            '\\' | '"' | '`' | '$' => { quoted.push('\\'); quoted.push(ch); },
            '%' => quoted.push_str("%%"),
            _ => quoted.push(ch),
        }
    }
    quoted.push('"');
    Ok(quoted.replace('\\', "\\\\"))
}

pub(crate) fn entry(executable: &Path, data: &Path) -> Result<String, String> {
    let executable = exec_argument(executable.to_str().ok_or("Executable path is not UTF-8")?)?;
    let data = exec_argument(data.to_str().ok_or("Data path is not UTF-8")?)?;
    // A fixed env launcher also lets GLib validate executable paths containing %:
    // its initial binary lookup happens before expansion of %% field escapes.
    Ok(format!("[Desktop Entry]\nType=Application\nVersion=1.0\nName=Clash Studio\nComment=Start Clash Studio at desktop login\nExec=/usr/bin/env -- {executable} --data-dir {data} --background\nTerminal=false\nX-GNOME-Autostart-enabled=true\n"))
}

fn configure_in(directory: &Path, enabled: bool, executable: &Path, data: &Path) -> Result<(), String> {
    let path = directory.join("studio.clash.desktop.desktop");
    if path.is_symlink() { return Err("Autostart entry must not be a symbolic link".into()); }
    if !enabled {
        return match fs::remove_file(path) { Ok(()) => Ok(()), Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()), Err(e) => Err(e.to_string()) };
    }
    let content = entry(executable, data)?;
    fs::create_dir_all(directory).map_err(|e| e.to_string())?;
    let temporary = directory.join(format!(".studio.clash.desktop.{}.tmp", std::process::id()));
    let result = (|| {
        use std::io::Write;
        let mut file = fs::OpenOptions::new().write(true).create_new(true).open(&temporary).map_err(|e| e.to_string())?;
        file.write_all(content.as_bytes()).and_then(|_| file.sync_all()).map_err(|e| e.to_string())?;
        fs::rename(&temporary, &path).map_err(|e| e.to_string())
    })();
    let _ = fs::remove_file(temporary);
    result
}

pub fn configure(enabled: bool) -> Result<(), String> {
    let config = std::env::var_os("XDG_CONFIG_HOME").map(PathBuf::from).filter(|p| p.is_absolute())
        .or_else(|| std::env::var_os("HOME").map(|p| PathBuf::from(p).join(".config")))
        .ok_or("Cannot locate user configuration directory")?;
    configure_in(&config.join("autostart"), enabled, &std::env::current_exe().map_err(|e| e.to_string())?, &super::paths::data_dir())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn quotes_paths_and_field_codes() {
        let text = entry(Path::new("/home/user/My App/ClashStudio"), Path::new("/home/user/数据 $x %f `x` \"a\" \\data")).unwrap();
        assert!(text.contains("Exec=/usr/bin/env -- \"/home/user/My App/ClashStudio\" --data-dir \""));
        assert!(text.contains("%%f"));
        assert!(text.contains("\\\\$x"));
        assert!(text.ends_with("X-GNOME-Autostart-enabled=true\n"));
        assert!(entry(Path::new("/tmp/a\nb"), Path::new("/tmp/data")).is_err());
    }
    #[test] fn enable_update_disable_preserves_other_entries() {
        let dir = std::env::temp_dir().join(format!("clash-autostart-test-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join("other.desktop"), "other").unwrap();
        configure_in(&dir, true, Path::new("/old/ClashStudio"), Path::new("/data")).unwrap();
        configure_in(&dir, true, Path::new("/new/ClashStudio"), Path::new("/data")).unwrap();
        assert!(fs::read_to_string(dir.join("studio.clash.desktop.desktop")).unwrap().contains("/new/ClashStudio"));
        configure_in(&dir, false, Path::new("/new/ClashStudio"), Path::new("/data")).unwrap();
        configure_in(&dir, false, Path::new("/new/ClashStudio"), Path::new("/data")).unwrap();
        assert_eq!(fs::read_to_string(dir.join("other.desktop")).unwrap(), "other");
        fs::remove_file(dir.join("other.desktop")).unwrap();
        fs::remove_dir(dir).unwrap();
    }
    #[cfg(target_os="linux")]
    #[test] fn gio_launch_preserves_special_paths() {
        use std::os::unix::fs::PermissionsExt;
        let dir=std::env::temp_dir().join(format!("clash-gio-autostart-{}",std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let executable=dir.join("Clash $test %f `literal` \"quoted\" \\tool");
        let data=dir.join("user data $HOME %u `literal` \"quoted\" \\data");
        let marker=dir.join("received-args");
        fs::write(&executable,format!("#!/bin/sh\nprintf '%s\\n' \"$@\" > '{}'\n",marker.display())).unwrap();
        fs::set_permissions(&executable,fs::Permissions::from_mode(0o700)).unwrap();
        configure_in(&dir,true,&executable,&data).unwrap();
        let result=std::process::Command::new("gio").arg("launch").arg(dir.join("studio.clash.desktop.desktop")).output().unwrap();
        assert!(result.status.success(),"{}",String::from_utf8_lossy(&result.stderr));
        for _ in 0..50 { if marker.exists(){break;} std::thread::sleep(std::time::Duration::from_millis(20)); }
        assert_eq!(fs::read_to_string(&marker).unwrap(),format!("--data-dir\n{}\n--background\n",data.display()));
        for file in [&marker,&executable,&dir.join("studio.clash.desktop.desktop")] { fs::remove_file(file).unwrap(); }
        fs::remove_dir(dir).unwrap();
    }
}
