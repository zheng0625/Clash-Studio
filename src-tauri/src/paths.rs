//! One path contract shared with run.py: resources are immutable, data is writable.
use std::path::PathBuf;

pub fn data_dir()->PathBuf{
    let args:Vec<_>=std::env::args_os().collect();
    if let Some(index)=args.iter().position(|arg|arg=="--data-dir"){if let Some(path)=args.get(index+1){return std::env::current_dir().unwrap_or_default().join(path);}}
    if let Some(path)=std::env::var_os("CLASH_STUDIO_DATA"){return std::env::current_dir().unwrap_or_default().join(path);}
    let root=super::project_root();
    if cfg!(windows)&&root.join("installed.json").is_file(){return std::env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_else(||std::env::var_os("USERPROFILE").map(PathBuf::from).unwrap_or_else(||root.clone()).join("AppData/Local")).join("ClashStudio");}
    if cfg!(windows)||root.join("portable.json").is_file(){return root.join("data");}
    let user=std::env::var_os("HOME").map(PathBuf::from).unwrap_or_else(||root.clone());
    if cfg!(target_os="macos"){return user.join("Library/Application Support/ClashStudio");}
    std::env::var_os("XDG_DATA_HOME").map(PathBuf::from).unwrap_or_else(||user.join(".local/share")).join("clash-studio")
}
pub fn python()->PathBuf{
    if let Some(path)=std::env::var_os("CLASH_STUDIO_PYTHON"){return PathBuf::from(path);}
    let root=super::project_root();
    if root.join("portable.json").is_file()||root.join("installed.json").is_file(){return root.join(if cfg!(windows){"runtime/python/python.exe"}else{"runtime/python/bin/python3"});}
    root.parent().unwrap_or(&root).join(if cfg!(windows){".venv/Scripts/python.exe"}else{".venv/bin/python3"})
}
