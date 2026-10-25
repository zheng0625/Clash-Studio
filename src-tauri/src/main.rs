#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use reqwest::blocking::Client;
mod desktop;
#[cfg(any(target_os="linux", test))]
mod linux_autostart;
#[cfg(target_os="linux")]
mod linux_desktop;
mod paths;
use serde::Serialize;
use serde_json::Value;
use std::{fs, io::Write, net::TcpListener, path::PathBuf, process::{Child, Command, Stdio}, sync::{Arc, Condvar, Mutex, atomic::{AtomicBool, Ordering}}, time::{Duration, Instant}};
use tauri::{Manager, State};
#[cfg(windows)]
use std::os::windows::process::CommandExt;

struct Backend {
    base: String,
    token: String,
    client: Client,
    child: Arc<Mutex<Option<Child>>>,
    stopping: AtomicBool,
    #[cfg(windows)]
    _job: BackendJob,
}

#[cfg(windows)]
struct BackendJob(isize);

#[cfg(windows)]
impl BackendJob {
    fn attach(child: &Child) -> Result<Self, Box<dyn std::error::Error>> {
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::System::JobObjects::*;
        unsafe {
            let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if job.is_null() { return Err(std::io::Error::last_os_error().into()); }
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(job, JobObjectExtendedLimitInformation, &info as *const _ as *const _, std::mem::size_of_val(&info) as u32) == 0 || AssignProcessToJobObject(job, child.as_raw_handle()) == 0 {
                CloseHandle(job as isize);
                return Err(std::io::Error::last_os_error().into());
            }
            Ok(Self(job as isize))
        }
    }
}

#[cfg(windows)]
impl Drop for BackendJob { fn drop(&mut self) { unsafe { CloseHandle(self.0); } } }

impl Backend {
    fn stop(&self) {
        if self.stopping.swap(true, Ordering::SeqCst) { return; }
        let started=Instant::now();
        let _ = self.client.post(format!("{}/api/client/prepare-exit", self.base))
            .header("X-Clash-Studio", "1").header("X-Clash-Desktop-Token", &self.token)
            .json(&serde_json::json!({})).timeout(Duration::from_secs(1)).send();
        let _ = self.client.post(format!("{}/api/shutdown", self.base))
            .header("X-Clash-Studio", "1").header("X-Clash-Desktop-Token", &self.token)
            .json(&serde_json::json!({})).timeout(Duration::from_secs(1)).send();
        if let Ok(mut slot) = self.child.lock() {
            if let Some(mut child) = slot.take() {
                let until = Instant::now() + Duration::from_secs(4);
                loop {
                    match child.try_wait() {
                        Ok(Some(_)) => break,
                        _ if Instant::now() > until => { let _ = child.kill(); let _ = child.wait(); break; },
                        _ => std::thread::sleep(Duration::from_millis(100)),
                    }
                }
            }
        }
        // If forced cleanup bypassed Python's lifespan, recover only our own proxy backup.
        let root=project_root();
        if paths::data_dir().join("system-proxy-backup.json").is_file(){
            let python=paths::python();
            let mut command=Command::new(python);
            command.args(["-I","-B"]).arg(root.join("run.py")).arg("--restore-proxy").env("CLASH_STUDIO_DATA", paths::data_dir()).current_dir(&root).stdout(Stdio::null()).stderr(Stdio::null());
            #[cfg(windows)] command.creation_flags(0x08000000);
            if let Ok(mut child)=command.spawn(){
                let until=Instant::now()+Duration::from_millis(1500);
                while child.try_wait().ok().flatten().is_none(){if Instant::now()>=until{let _=child.kill();let _=child.wait();break;}std::thread::sleep(Duration::from_millis(25));}
            }
        }
        startup_log(started,"exit_cleanup_complete");
    }
}

struct Shutdown(AtomicBool);

#[derive(Clone)]
struct Startup(Arc<StartupInner>);
struct StartupInner {
    result: Mutex<Option<Result<Arc<Backend>, String>>>,
    changed: Condvar,
    cancelled: AtomicBool,
}
impl Startup {
    fn new() -> Self { Self(Arc::new(StartupInner { result: Mutex::new(None), changed: Condvar::new(), cancelled: AtomicBool::new(false) })) }
    fn wait(&self) -> Result<Arc<Backend>, String> {
        let slot = self.0.result.lock().map_err(|_| "Startup state unavailable")?;
        let (slot, _) = self.0.changed.wait_timeout_while(slot, Duration::from_secs(30), |value| value.is_none()).map_err(|_| "Startup state unavailable")?;
        slot.as_ref().cloned().unwrap_or_else(|| Err("Backend startup timed out".into()))
    }
    fn stop(&self) {
        self.0.cancelled.store(true, Ordering::SeqCst);
        if let Ok(backend) = self.wait() { backend.stop(); }
    }
}

#[derive(Serialize)]
struct StartupStatus { phase: &'static str }
#[tauri::command]
fn startup_status(startup: State<'_, Startup>) -> StartupStatus {
    let phase = match startup.0.result.lock() {
        Ok(slot) => match slot.as_ref() { None => "starting", Some(Ok(_)) => "ready", Some(Err(_)) => "error" },
        Err(_) => "error",
    };
    StartupStatus { phase }
}

fn startup_log(started: Instant, stage: &str) {
    let path = paths::data_dir().join("startup.log");
    if let Ok(mut file) = fs::OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "pid={} elapsed_ms={} {}", std::process::id(), started.elapsed().as_millis(), stage);
    }
}

#[tauri::command]
fn system_locale() -> &'static str {
    #[cfg(windows)] { if unsafe { GetUserDefaultUILanguage() } & 0x3ff == 0x04 { "zh-CN" } else { "en" } }
    #[cfg(not(windows))] {
        let language=["LC_ALL","LC_MESSAGES","LANG"].iter().filter_map(|key|std::env::var(key).ok()).find(|value|!value.is_empty()).unwrap_or_default();
        if language.to_lowercase().starts_with("zh"){"zh-CN"}else{"en"}
    }
}

fn begin_shutdown(app: tauri::AppHandle) {
    if let Some(flag) = app.try_state::<Shutdown>() {
        if flag.0.swap(true, Ordering::SeqCst) { return; }
    }
    if let Some(startup) = app.try_state::<Startup>() { startup.0.cancelled.store(true, Ordering::SeqCst); }
    // Remove the visible window promptly; perform bounded cleanup off the UI thread.
    if let Some(window) = app.get_webview_window("main") { let _ = window.hide(); }
    std::thread::spawn(move || {
        if let Some(startup) = app.try_state::<Startup>() { startup.stop(); }
        app.exit(0);
    });
}

#[tauri::command]
fn quit_app(app: tauri::AppHandle) { begin_shutdown(app); }

#[derive(Serialize)]
struct DesktopInfo { backend_base: String, version: &'static str, desktop: bool }

#[tauri::command]
async fn desktop_info(startup: State<'_, Startup>) -> Result<DesktopInfo, String> {
    let startup = startup.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let backend = startup.wait()?;
        Ok(DesktopInfo { backend_base: backend.base.clone(), version: env!("CARGO_PKG_VERSION"), desktop: true })
    }).await.map_err(|e| e.to_string())?
}

#[tauri::command]
async fn backend_request(startup: State<'_, Startup>, path: String, method: String, body: Option<Value>) -> Result<Value, String> {
    if !allowed_path(&path) {
        return Err("不允许的本机接口路径".into());
    }
    if !["GET", "POST", "PUT", "PATCH", "DELETE"].contains(&method.as_str()) {
        return Err("不允许的请求方法".into());
    }
    let startup = startup.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let backend = startup.wait()?;
        let base = backend.base.clone();
        let token = backend.token.clone();
        let client = backend.client.clone();
        let parsed = reqwest::Method::from_bytes(method.as_bytes()).map_err(|e| e.to_string())?;
        let mut request = client.request(parsed, format!("{base}{path}"))
            .header("X-Clash-Studio", "1").header("X-Clash-Desktop-Token", token);
        if let Some(data) = body { request = request.json(&data); }
        let response = request.send().map_err(|_| "本机配置服务暂时无法连接".to_string())?;
        let status = response.status().as_u16();
        let payload: Value = response.json().map_err(|_| "本机服务返回了无效响应".to_string())?;
        Ok(serde_json::json!({"status": status, "data": payload}))
    }).await.map_err(|e| e.to_string())?
}

fn allowed_path(path: &str) -> bool {
    path.starts_with("/api/") && !path.contains("..") && !path.contains('\\') && !path.contains("//")
}

#[cfg(windows)]
#[link(name = "shell32")]
extern "system" {
    fn ShellExecuteW(hwnd: isize, operation: *const u16, file: *const u16, parameters: *const u16, directory: *const u16, show: i32) -> isize;
    fn IsUserAnAdmin() -> i32;
}

#[cfg(windows)]
#[link(name = "kernel32")]
extern "system" {
    fn GetUserDefaultUILanguage() -> u16;
    fn OpenProcess(access: u32, inherit: i32, pid: u32) -> isize;
    fn WaitForSingleObject(handle: isize, milliseconds: u32) -> u32;
    fn CloseHandle(handle: isize) -> i32;
}

#[tauri::command]
fn restart_elevated(app: tauri::AppHandle) -> Result<(), String> {
    #[cfg(windows)] {
        use std::os::windows::ffi::OsStrExt;
        let executable = std::env::current_exe().map_err(|e| e.to_string())?;
        let file: Vec<u16> = executable.as_os_str().encode_wide().chain(Some(0)).collect();
        let verb: Vec<u16> = "runas\0".encode_utf16().collect();
        let args: Vec<u16> = format!("--wait-for {} --data-dir \"{}\"\0", std::process::id(),paths::data_dir().display()).encode_utf16().collect();
        let result = unsafe { ShellExecuteW(0, verb.as_ptr(), file.as_ptr(), args.as_ptr(), std::ptr::null(), 1) };
        if result <= 32 { return Err("管理员重启未完成；可能取消了 Windows 确认".into()); }
        app.exit(0);
        Ok(())
    }
    #[cfg(not(windows))] { let _ = app; Err("当前仅支持 Windows".into()) }
}

fn project_root() -> PathBuf {
    // A portable installation must not resolve into a developer checkout.
    if let Ok(executable) = std::env::current_exe() {
        if let Some(dir) = executable.parent() {
            if dir.join("portable.json").is_file() { return dir.into(); }
        }
    }
    if let Ok(path) = std::env::var("CLASH_STUDIO_ROOT") { return path.into(); }
    if let Ok(executable) = std::env::current_exe() {
        for dir in executable.ancestors().skip(1).take(5) {
            if dir.join("Resources/run.py").is_file() { return dir.join("Resources"); }
            if dir.join("run.py").is_file() && dir.join("server").is_dir() { return dir.into(); }
        }
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().into()
}

fn start_backend(cancelled: &AtomicBool) -> Result<Backend, Box<dyn std::error::Error>> {
    if cancelled.load(Ordering::SeqCst) { return Err("Startup cancelled".into()); }
    let root = project_root();
    let python = paths::python();
    if !python.is_file() { return Err("Missing Python runtime; extract the complete portable ZIP or restore the development environment".into()); }
    fs::create_dir_all(paths::data_dir())?;
    let log = fs::OpenOptions::new().create(true).append(true).open(paths::data_dir().join("tauri-backend.log"))?;
    let port = TcpListener::bind("127.0.0.1:0")?.local_addr()?.port();
    let token = uuid::Uuid::new_v4().to_string();
    let mut command = Command::new(python);
    command.arg("-I").arg("-B").arg(root.join("run.py")).args(["--no-window", "--desktop", "--port", &port.to_string()])
        .env("CLASH_STUDIO_DESKTOP_TOKEN", &token).env("CLASH_STUDIO_DATA", paths::data_dir()).current_dir(&root)
        .stdout(Stdio::from(log.try_clone()?)).stderr(Stdio::from(log));
    #[cfg(windows)] command.creation_flags(0x08000000);
    let mut child = command.spawn()?;
    #[cfg(windows)]
    let job = match BackendJob::attach(&child) { Ok(job) => job, Err(error) => { let _ = child.kill(); return Err(error); } };
    let base = format!("http://127.0.0.1:{port}");
    let client = Client::builder().no_proxy().timeout(Duration::from_secs(120)).build()?;
    let until = Instant::now() + Duration::from_secs(25);
    loop {
        if cancelled.load(Ordering::SeqCst) { let _ = child.kill(); let _ = child.wait(); return Err("Startup cancelled".into()); }
        if child.try_wait()?.is_some() { return Err("Backend exited; see data/tauri-backend.log".into()); }
        if client.get(format!("{base}/api/client/info")).header("X-Clash-Desktop-Token", &token)
            .timeout(Duration::from_millis(400)).send().map(|r| r.status().is_success()).unwrap_or(false) { break; }
        if Instant::now() > until { let _ = child.kill(); return Err("Backend startup timed out".into()); }
        std::thread::sleep(Duration::from_millis(150));
    }
    Ok(Backend { base, token, client, child: Arc::new(Mutex::new(Some(child))), stopping: AtomicBool::new(false), #[cfg(windows)] _job: job })
}

fn main() {
    let started = Instant::now();
    #[cfg(windows)] {
        let args: Vec<String> = std::env::args().collect();
        if let Some(index) = args.iter().position(|s| s == "--wait-for") {
            if let Some(pid) = args.get(index + 1).and_then(|s| s.parse::<u32>().ok()) {
                unsafe { let handle = OpenProcess(0x00100000, 0, pid); if handle != 0 { WaitForSingleObject(handle, 20000); CloseHandle(handle); } }
            }
        }
    }
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, args, _cwd| {
            if args.iter().any(|arg| arg == "--quit") { begin_shutdown(app.clone()); return; }
            desktop::show(app);
        }))
        .setup(move |app| {
            app.manage(Shutdown(AtomicBool::new(false)));
            if std::env::args().any(|arg| arg == "--quit") { app.handle().exit(0); return Ok(()); }
            fs::create_dir_all(paths::data_dir())?;
            #[cfg(target_os="linux")]
            if let Err(error)=linux_desktop::install(){eprintln!("Linux desktop integration: {error}");}
            desktop::initialize(app.handle())?;
            let startup = Startup::new();
            app.manage(startup.clone());
            desktop::start_tray_sync(app.handle().clone());
            startup_log(started, "backend_start");
            // Start Python concurrently with WebView creation; never wait on the UI thread.
            std::thread::spawn(move || {
                let result = start_backend(&startup.0.cancelled).map(Arc::new).map_err(|error| error.to_string());
                match &result {
                    Ok(_) => startup_log(started, "backend_ready"),
                    Err(error) => startup_log(started, &format!("backend_error: {error}")),
                }
                if let Ok(mut slot) = startup.0.result.lock() { *slot = Some(result); startup.0.changed.notify_all(); }
            });
            let mut window = tauri::WebviewWindowBuilder::from_config(app.handle(), &app.config().app.windows[0])?;
            window = window.data_directory(paths::data_dir().join("webview2"));
            window.visible(!desktop::background_requested()).initialization_script(format!("window.__CLASH_SYSTEM_LANGUAGE__ = {:?};", system_locale())).build()?;
            startup_log(started, "window_created");
            #[cfg(windows)] {
                // Lets the stop shortcut identify this installation even when
                // Windows hides an elevated process's executable path.
                let owner = serde_json::json!({"pid": std::process::id(),
                    "executable": std::env::current_exe()?, "elevated": unsafe { IsUserAnAdmin() != 0 }});
                fs::write(paths::data_dir().join("desktop-instance.json"), owner.to_string())?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_request, desktop_info, startup_status, system_locale, restart_elevated, quit_app, desktop::desktop_preferences, desktop::set_desktop_preferences, desktop::set_desktop_language, desktop::close_desktop, desktop::desktop_ready, desktop::tray_menu_state, desktop::tray_menu_action])
        .build(tauri::generate_context!()).expect("Unable to launch Clash Studio");
    app.run(|app, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            if let Some(startup) = app.try_state::<Startup>() { startup.stop(); }
            let path = paths::data_dir().join("desktop-instance.json");
            if let Ok(value) = fs::read_to_string(&path) {
                if serde_json::from_str::<Value>(&value).ok().and_then(|v| v["pid"].as_u64()) == Some(std::process::id() as u64) {
                    let _ = fs::remove_file(path);
                }
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::allowed_path;
    #[test]
    fn backend_bridge_only_allows_own_api_paths() {
        assert!(allowed_path("/api/subscriptions/abc?revision=3"));
        assert!(allowed_path("/api/client/runtime/proxies/Work"));
        for path in ["https://example.org/api/", "//example.org/api/", "/api/../secret", "/api/a\\b", "/assets/file"] {
            assert!(!allowed_path(path));
        }
    }
}
