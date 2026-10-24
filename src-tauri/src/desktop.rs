use serde::{Deserialize, Serialize};
use std::{fs, sync::{Mutex, atomic::{AtomicBool, Ordering}}};
#[cfg(windows)]
use std::process::Command;
use tauri::{Emitter, Manager, State, menu::{Menu, MenuItem, CheckMenuItem, Submenu}, tray::{TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState}};

#[derive(Clone, Copy, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Preferences { pub resident: bool, pub autostart: bool }
impl Default for Preferences{fn default()->Self{Self{resident:true,autostart:false}}}
pub struct DesktopState { prefs: Mutex<Preferences>, ready: AtomicBool }
struct TrayControls{menu:Mutex<Menu<tauri::Wry>>,menu_signature:Mutex<String>,open:MenuItem<tauri::Wry>,quit:MenuItem<tauri::Wry>,routes:Submenu<tauri::Wry>,transports:Submenu<tauri::Wry>,last:Mutex<serde_json::Value>,toggle:CheckMenuItem<tauri::Wry>,status:MenuItem<tauri::Wry>,routing:Vec<(String,CheckMenuItem<tauri::Wry>)>,transport:Vec<(String,CheckMenuItem<tauri::Wry>)>,busy:AtomicBool}

fn resolve_language(preference:&str,system:&str)->String{
    match preference{"zh-CN"=>"zh-CN","en"=>"en",_=>system}.to_owned()
}
fn desktop_locale()->String{
    let preference=fs::read(super::paths::data_dir().join("desktop-language.json")).ok()
        .and_then(|s|serde_json::from_slice::<String>(&s).ok()).unwrap_or_else(||"auto".into());
    resolve_language(&preference,super::system_locale())
}
#[tauri::command]
pub fn set_desktop_language(app:tauri::AppHandle,language:String)->Result<(),String>{
    if !matches!(language.as_str(),"auto"|"zh-CN"|"en"){return Err("Invalid language".into())}
    let path=super::paths::data_dir().join("desktop-language.json");
    let temporary=path.with_extension("tmp");
    fs::write(&temporary,serde_json::to_vec(&language).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
    fs::rename(&temporary,&path).map_err(|e|e.to_string())?;
    let value=app.state::<TrayControls>().last.lock().map_err(|_|"Tray state unavailable")?.clone();
    sync_tray(&app,&value);
    Ok(())
}
fn tray_request(app:&tauri::AppHandle,action:Option<&str>)->Result<serde_json::Value,String>{
    let startup=app.state::<super::Startup>();
    let backend=startup.wait()?;
    let request=if let Some(action)=action{backend.client.post(format!("{}/api/client/tray/action",backend.base)).json(&serde_json::json!({"action":action}))}else{backend.client.get(format!("{}/api/client/tray",backend.base))};
    let response=request.header("X-Clash-Studio","1").header("X-Clash-Desktop-Token",&backend.token)
        .timeout(std::time::Duration::from_secs(if action.is_some(){120}else{2})).send().map_err(|_|"托盘操作未完成，请检查本机服务".to_string())?;
    let ok=response.status().is_success();let value:serde_json::Value=response.json().map_err(|_|"本机服务返回无效响应")?;
    if ok{Ok(value)}else{Err(value["detail"].as_str().unwrap_or("托盘操作失败，请在主窗口检查配置").into())}
}
fn sync_tray(app:&tauri::AppHandle,value:&serde_json::Value){
    if let Some(tray)=app.tray_by_id("main-tray"){let _=tray.set_tooltip(Some("Clash Studio"));}
    let controls=app.state::<TrayControls>();let enabled=value["enabled"].as_bool().unwrap_or(false);let busy=controls.busy.load(Ordering::SeqCst);
    let chinese=desktop_locale()=="zh-CN";
    if let Ok(mut last)=controls.last.lock(){*last=value.clone();}
    let _=controls.open.set_text(if chinese{"打开 Clash Studio"}else{"Open Clash Studio"});
    let _=controls.quit.set_text(if chinese{"退出"}else{"Quit"});
    let _=controls.toggle.set_text(if chinese{"开启代理"}else{"Enable proxy"});
    let _=controls.routes.set_text(if chinese{"代理模式"}else{"Proxy mode"});
    let _=controls.transports.set_text(if chinese{"接管方式"}else{"Traffic capture"});
    for (mode,item) in &controls.routing{let _=item.set_text(match (mode.as_str(),chinese){("rule",true)=>"规则",("global",true)=>"全局",("direct",true)=>"直连",("rule",false)=>"Rule",("global",false)=>"Global",_=>"Direct"});}
    for (mode,item) in &controls.transport{let _=item.set_text(if mode=="tun"{"TUN"}else if chinese{"系统代理"}else{"System proxy"});}
    let _=controls.status.set_text(if enabled{if chinese{"代理已开启"}else{"Proxy enabled"}}else{if chinese{"代理未开启"}else{"Proxy disabled"}});
    let _=controls.toggle.set_checked(enabled);let _=controls.toggle.set_enabled(!busy&&(enabled||value["can_start"].as_bool().unwrap_or(false)));
    for (mode,item) in &controls.routing{let _=item.set_checked(value["routing_mode"].as_str()==Some(mode));let _=item.set_enabled(!busy);}
    for (mode,item) in &controls.transport{let supported=value["capabilities"][if mode=="tun"{"tun"}else{"system_proxy"}].as_bool().unwrap_or(true);let _=item.set_checked(supported&&value["proxy_mode"].as_str()==Some(mode));let _=item.set_enabled(!busy&&supported);}
    #[cfg(not(windows))]
    if let Ok(mut previous)=controls.menu_signature.lock(){
        let signature=serde_json::json!([chinese,busy,value]).to_string();
        if *previous!=signature{
            // AppIndicator exports a snapshot; reattach a fresh GTK menu when labels or proxy state change.
            if let Ok(menu)=Menu::with_items(app,&[&controls.open,&controls.status,&controls.toggle,&controls.routes,&controls.transports,&controls.quit]){
                if let Some(tray)=app.tray_by_id("main-tray"){
                    if tray.set_menu(Some(menu.clone())).is_ok(){
                        if let Ok(mut retained)=controls.menu.lock(){*retained=menu;}
                        *previous=signature;
                    }
                }
            }
        }
    };

}
fn tray_action(app:&tauri::AppHandle,action:&str){
    let controls=app.state::<TrayControls>();if controls.busy.swap(true,Ordering::SeqCst){return}
    let _=controls.toggle.set_enabled(false);for (_,item) in controls.routing.iter().chain(controls.transport.iter()){let _=item.set_enabled(false);}
    let app=app.clone();let action=action.to_owned();
    std::thread::spawn(move||{
        let result=tray_request(&app,Some(&action));app.state::<TrayControls>().busy.store(false,Ordering::SeqCst);
        match result{Ok(value)=>{sync_tray(&app,&value);let _=app.emit("desktop-tray-updated",value);},Err(error)=>{
            show(&app);let _=app.emit("desktop-tray-error",error.clone());
            if let Some(tray)=app.tray_by_id("main-tray"){let _=tray.set_tooltip(Some(format!("Clash Studio · {error}")));}
            if let Ok(value)=tray_request(&app,None){sync_tray(&app,&value);}
        }}
    });
}
pub fn start_tray_sync(app:tauri::AppHandle){std::thread::spawn(move||{
    let startup=app.state::<super::Startup>().inner().clone();if startup.wait().is_err(){return}
    while !startup.0.cancelled.load(Ordering::SeqCst){
        if let Ok(value)=tray_request(&app,None){sync_tray(&app,&value);}
        std::thread::sleep(std::time::Duration::from_secs(2));
    }
});}

fn read_preferences() -> Preferences {
    fs::read(super::paths::data_dir().join("desktop-settings.json")).ok()
        .and_then(|s| serde_json::from_slice(&s).ok()).unwrap_or_default()
}
#[cfg(any(windows,test))]
fn autostart_command() -> Result<String, String> {
    Ok(format!("\"{}\" --data-dir \"{}\" --background",std::env::current_exe().map_err(|e|e.to_string())?.display(),super::paths::data_dir().display()))
}
fn configure_autostart(enabled: bool) -> Result<(), String> {
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        let key=r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run";
        let mut command=Command::new("reg.exe");
        if enabled { command.args(["add",key,"/v","ClashStudio","/t","REG_SZ","/d",&autostart_command()?,"/f"]); }
        else {
            let mut query=Command::new("reg.exe");
            let found=query.args(["query",key,"/v","ClashStudio"]).creation_flags(0x08000000).output().map_err(|e|e.to_string())?;
            if !found.status.success() { return Ok(()); }
            command.args(["delete",key,"/v","ClashStudio","/f"]);
        }
        let result=command.creation_flags(0x08000000).output().map_err(|e|e.to_string())?;
        if !result.status.success() { return Err("无法更新当前用户的开机自启设置".into()); }
        Ok(())
    }
    #[cfg(target_os="linux")] { super::linux_autostart::configure(enabled) }
    #[cfg(not(any(windows,target_os="linux")))] { let _=enabled; Err("当前平台不支持登录自启".into()) }
}
pub fn show(app:&tauri::AppHandle) {
    if let Some(window)=app.get_webview_window("main") { let _=window.show();let _=window.unminimize();let _=window.set_focus(); }
}
fn hide_menu(app:&tauri::AppHandle){if let Some(window)=app.get_webview_window("tray-menu"){let _=window.hide();}}
fn show_menu(app:&tauri::AppHandle,position:tauri::PhysicalPosition<f64>)->Result<(),String>{
    let window=if let Some(window)=app.get_webview_window("tray-menu"){window}else{
        let mut builder=tauri::WebviewWindowBuilder::new(app,"tray-menu",tauri::WebviewUrl::App("index.html?tray".into()))
            .title("Clash Studio tray").inner_size(304.0,386.0).decorations(false).transparent(true).shadow(false)
            .resizable(false).skip_taskbar(true).always_on_top(true).visible(false)
            .initialization_script(format!("window.__CLASH_SYSTEM_LANGUAGE__ = {:?};",super::system_locale()));
        builder=builder.data_directory(super::paths::data_dir().join("webview2"));
        let window=builder.build().map_err(|e|e.to_string())?;
        let handle=app.clone();window.on_window_event(move|event|{if matches!(event,tauri::WindowEvent::Focused(false)){hide_menu(&handle);}});
        window
    };
    let monitor=window.monitor_from_point(position.x,position.y).map_err(|e|e.to_string())?.or(window.primary_monitor().map_err(|e|e.to_string())?);
    let scale=monitor.as_ref().map(|m|m.scale_factor()).unwrap_or(1.0);
    let (width,height)=(304.0*scale,386.0*scale);
    let mut x=position.x-width+12.0*scale;let mut y=position.y-height-8.0*scale;
    if let Some(monitor)=monitor{let area=monitor.work_area();let left=area.position.x as f64;let top=area.position.y as f64;
        x=x.clamp(left,(left+area.size.width as f64-width).max(left));y=y.clamp(top,(top+area.size.height as f64-height).max(top));}
    window.set_position(tauri::PhysicalPosition::new(x as i32,y as i32)).map_err(|e|e.to_string())?;
    window.show().map_err(|e|e.to_string())?;window.set_focus().map_err(|e|e.to_string())?;let _=window.emit("tray-menu-open",());Ok(())
}
#[tauri::command]
pub async fn tray_menu_state(app:tauri::AppHandle)->Result<serde_json::Value,String>{
    tauri::async_runtime::spawn_blocking(move||{let mut state=tray_request(&app,None)?;state["busy"]=serde_json::json!(app.state::<TrayControls>().busy.load(Ordering::SeqCst));Ok(state)}).await.map_err(|e|e.to_string())?
}
#[tauri::command]
pub fn tray_menu_action(app:tauri::AppHandle,action:String)->Result<(),String>{
    match action.as_str(){
        "hide"=>hide_menu(&app),"open"=>{hide_menu(&app);show(&app);},
        "quit"=>{hide_menu(&app);if app.state::<DesktopState>().ready.load(Ordering::SeqCst){show(&app);let _=app.emit("desktop-quit-request",());}else{super::begin_shutdown(app.clone());}},
        "toggle"|"rule"|"global"|"direct"|"system"|"tun"=>tray_action(&app,&action),
        _=>return Err("Invalid tray action".into())
    }Ok(())
}
pub fn initialize(app:&tauri::AppHandle) -> tauri::Result<()> {
    let prefs=read_preferences();
    #[cfg(target_os="linux")]
    if prefs.autostart { if let Err(error)=configure_autostart(true) { eprintln!("Clash Studio autostart: {error}"); } }
    app.manage(DesktopState{prefs:Mutex::new(prefs),ready:AtomicBool::new(false)});
    let chinese=desktop_locale()=="zh-CN";
    let open=MenuItem::with_id(app,"open",if chinese{"打开 Clash Studio"}else{"Open Clash Studio"},true,None::<&str>)?;
    let quit=MenuItem::with_id(app,"quit",if chinese{"退出"}else{"Quit"},true,None::<&str>)?;
    let status=MenuItem::with_id(app,"proxy-status",if chinese{"正在读取代理状态…"}else{"Reading proxy status…"},false,None::<&str>)?;
    let toggle=CheckMenuItem::with_id(app,"proxy-toggle",if chinese{"开启代理"}else{"Enable proxy"},false,false,None::<&str>)?;
    let rule=CheckMenuItem::with_id(app,"route-rule",if chinese{"规则"}else{"Rule"},false,false,None::<&str>)?;
    let global=CheckMenuItem::with_id(app,"route-global",if chinese{"全局"}else{"Global"},false,false,None::<&str>)?;
    let direct=CheckMenuItem::with_id(app,"route-direct",if chinese{"直连"}else{"Direct"},false,false,None::<&str>)?;
    let system=CheckMenuItem::with_id(app,"transport-system",if chinese{"系统代理"}else{"System proxy"},false,false,None::<&str>)?;
    let tun=CheckMenuItem::with_id(app,"transport-tun","TUN",false,false,None::<&str>)?;
    let routes=Submenu::with_items(app,if chinese{"代理模式"}else{"Proxy mode"},true,&[&rule,&global,&direct])?;
    let transports=Submenu::with_items(app,if chinese{"接管方式"}else{"Traffic capture"},true,&[&system,&tun])?;
    let _menu=Menu::with_items(app,&[&open,&status,&toggle,&routes,&transports,&quit])?;
    app.manage(TrayControls{menu:Mutex::new(_menu.clone()),menu_signature:Mutex::new(String::new()),open,quit,routes,transports,last:Mutex::new(serde_json::json!({})),toggle,status,routing:vec![("rule".into(),rule),("global".into(),global),("direct".into(),direct)],transport:vec![("system".into(),system),("tun".into(),tun)],busy:AtomicBool::new(false)});
    let mut builder=TrayIconBuilder::with_id("main-tray").tooltip("Clash Studio").show_menu_on_left_click(false);
    #[cfg(not(windows))] {builder=builder.menu(&_menu);}
    if let Some(icon)=app.default_window_icon(){builder=builder.icon(icon.clone());}
    let tray=builder.on_menu_event(|app,event|match event.id.as_ref(){
        "open"=>show(app),
        "proxy-toggle"=>tray_action(app,"toggle"),
        "route-rule"=>tray_action(app,"rule"),"route-global"=>tray_action(app,"global"),"route-direct"=>tray_action(app,"direct"),
        "transport-system"=>tray_action(app,"system"),"transport-tun"=>tray_action(app,"tun"),
        "quit"=>{
            if app.state::<DesktopState>().ready.load(Ordering::SeqCst){
                show(app);let _=app.emit("desktop-quit-request",());
            }else{super::begin_shutdown(app.clone());}
        },_=>{}
    }).on_tray_icon_event(|tray,event|{
        if let TrayIconEvent::Click{button:MouseButton::Right,button_state:MouseButtonState::Up,position,..}=&event{if let Err(error)=show_menu(tray.app_handle(),*position){show(tray.app_handle());let _=tray.app_handle().emit("desktop-tray-error",error);}}
        if matches!(event,TrayIconEvent::Click{button:MouseButton::Left,button_state:MouseButtonState::Up,..}){show(tray.app_handle());}
    }).build(app)?;
    tray.set_visible(prefs.resident)?;
    Ok(())
}
#[tauri::command]
pub fn desktop_preferences(state:State<'_,DesktopState>)->Result<Preferences,String>{
    state.prefs.lock().map(|p|*p).map_err(|_|"桌面设置不可用".into())
}
#[tauri::command]
pub fn set_desktop_preferences(app:tauri::AppHandle,state:State<'_,DesktopState>,preferences:Preferences)->Result<Preferences,String>{
    let mut prefs=state.prefs.lock().map_err(|_|"桌面设置不可用")?;
    let old=*prefs;
    if old.autostart!=preferences.autostart{configure_autostart(preferences.autostart)?;}
    let result=(||->Result<(),String>{
        if let Some(tray)=app.tray_by_id("main-tray"){tray.set_visible(preferences.resident).map_err(|e|e.to_string())?;}
        else if preferences.resident{return Err("托盘图标不可用，无法开启后台驻留".into());}
        let path=super::paths::data_dir().join("desktop-settings.json");
        let temporary=path.with_extension("tmp");
        fs::write(&temporary,serde_json::to_vec(&preferences).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
        fs::rename(temporary,path).map_err(|e|e.to_string())?;
        Ok(())
    })();
    if let Err(error)=result{
        if old.autostart!=preferences.autostart{let _=configure_autostart(old.autostart);}
        if let Some(tray)=app.tray_by_id("main-tray"){let _=tray.set_visible(old.resident);}
        return Err(error);
    }
    *prefs=preferences;Ok(preferences)
}
#[tauri::command]
pub fn desktop_ready(state:State<'_,DesktopState>){state.ready.store(true,Ordering::SeqCst);super::startup_log(std::time::Instant::now(),"frontend_ready");}
#[tauri::command]
pub fn close_desktop(app:tauri::AppHandle,state:State<'_,DesktopState>)->Result<bool,String>{
    let resident=state.prefs.lock().map_err(|_|"桌面设置不可用")?.resident;
    if resident {
        if let Some(tray)=app.tray_by_id("main-tray"){tray.set_visible(true).map_err(|e|e.to_string())?;}
        else{return Err("托盘图标不可用".into());}
        if let Some(window)=app.get_webview_window("main"){window.hide().map_err(|e|e.to_string())?;}
    }else{super::begin_shutdown(app);}
    Ok(resident)
}
pub fn background_requested()->bool{read_preferences().resident&&std::env::args().any(|a|a=="--background")}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]fn selected_language_overrides_system(){assert_eq!(resolve_language("zh-CN","en"),"zh-CN");assert_eq!(resolve_language("en","zh-CN"),"en");assert_eq!(resolve_language("auto","zh-CN"),"zh-CN");assert_eq!(resolve_language("auto","en"),"en");}
    #[test]fn resident_is_default_and_autostart_is_opt_in(){let p:Preferences=serde_json::from_str("{}").unwrap();assert!(p.resident&&!p.autostart);let old:Preferences=serde_json::from_str(r#"{"resident":false,"autostart":false}"#).unwrap();assert!(!old.resident);}
    #[test]fn preferences_round_trip(){let p:Preferences=serde_json::from_str(r#"{"resident":true,"autostart":false}"#).unwrap();assert!(p.resident&&!p.autostart);let command=autostart_command().unwrap();assert!(command.contains("--data-dir \""));assert!(command.ends_with("\" --background"));}
}
