import { ref } from 'vue'
import { androidRequest } from './android'
declare global {interface Window {__clashAndroidSystemDark?:boolean}}

export type ClientTheme={accent:string;background:string;surface:string;text:string;sidebar:string;sidebarText:string;secondary:string;selected:string;border:string;success:string;warning:string;error:string}
export const darkTheme:ClientTheme={background:'#101318',sidebar:'#171B22',surface:'#1C222B',selected:'#262E39',border:'#343D49',text:'#F0F3F8',secondary:'#A2ACBA',sidebarText:'#F0F3F8',accent:'#60A5FA',success:'#4ADE80',warning:'#F59E0B',error:'#EF4444'}
export const lightTheme:ClientTheme={background:'#F5F7FA',sidebar:'#EBEFF4',surface:'#FFFFFF',selected:'#E7EDF5',border:'#D7DFE9',text:'#182333',secondary:'#586679',sidebarText:'#182333',accent:'#2563EB',success:'#15803D',warning:'#A16207',error:'#DC2626'}
export const defaultTheme=lightTheme
export const softBackground=ref(true)
export function setSoftBackground(enabled:boolean){
  softBackground.value=enabled
  document.documentElement.dataset.softBackground=enabled?'on':'off'
  try{localStorage.setItem('clash-studio-soft-background-v1',String(enabled))}catch{/* Keep the setting for this session. */}
}
export const themeFields:{key:keyof ClientTheme;label:string}[]=[
  {key:'accent',label:'主色'},{key:'background',label:'页面背景'},{key:'surface',label:'卡片背景'},
  {key:'text',label:'正文文字'},{key:'secondary',label:'次要文字'},{key:'sidebar',label:'侧栏与标题栏'},{key:'sidebarText',label:'侧栏文字'},
  {key:'selected',label:'悬停与选中背景'},{key:'border',label:'边框与分割线'},
  {key:'success',label:'成功状态'},{key:'warning',label:'警告状态'},{key:'error',label:'错误状态'},
]
export const themePresets=[{name:'浅色主题',colors:lightTheme},{name:'深色主题',colors:darkTheme}]
const storageKey='clash-studio-client-theme-v1'
export const currentTheme=ref<ClientTheme>({...defaultTheme})
let automatic:boolean|null=null
export function validHex(value:unknown):value is string{return typeof value==='string'&&/^#[0-9a-f]{6}$/i.test(value)}
function rgb(hex:string){return [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16))}
function luminance(hex:string){const c=rgb(hex).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return .2126*c[0]!+.7152*c[1]!+.0722*c[2]!}
export function contrast(a:string,b:string){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)}
function mix(a:string,b:string,t:number){const x=rgb(a),y=rgb(b);return '#'+x.map((v,i)=>Math.round(v+(y[i]!-v)*t).toString(16).padStart(2,'0')).join('')}
export function readableCoverage(surface:string,text:string,requested:number){for(let p=Math.ceil(requested);p<=100;p++){if(contrast(text,mix(surface,'#000000',1-p/100))>=4.5&&contrast(text,mix(surface,'#ffffff',1-p/100))>=4.5)return p}return 100}
/* Theme mode: system / light / dark are the built-in options; 'custom' is
   entered by saving a palette and leaves when a built-in mode is chosen. */
export type ThemeMode='system'|'light'|'dark'|'custom'
const modeKey='clash-studio-theme-mode-v1'
export const themeMode=ref<ThemeMode>('system')
export const systemDark=ref(false)
export const themeEpoch=ref(0)
function restoreMode():ThemeMode{
  const stored=localStorage.getItem(modeKey)
  if(stored==='system'||stored==='light'||stored==='dark'||stored==='custom')return stored
  // Backward compatibility: a previously saved palette keeps its look.
  return localStorage.getItem(storageKey)?'custom':'system'
}
function currentDark(){return themeMode.value==='dark'||(themeMode.value==='system'&&systemDark.value)}
export function effectiveTheme(){
  if(automatic!==null)return {...(automatic?darkTheme:lightTheme),accent:currentTheme.value.accent}
  if(themeMode.value==='custom')return currentTheme.value
  return {...(currentDark()?darkTheme:lightTheme),accent:currentTheme.value.accent}
}
export function secondaryColor(theme:ClientTheme,_photoAutomatic=automatic!==null){return theme.secondary}
export function themeError(theme:ClientTheme){
  if(!themeFields.every(f=>validHex(theme[f.key])))return '请输入有效的六位十六进制颜色，例如 #7659d5。'
  if([theme.text,theme.secondary].some(c=>Math.min(contrast(c,theme.surface),contrast(c,theme.background),contrast(c,theme.selected))<4.5))return '正文与辅助文字在背景、面板和选中区域的对比度须达到 4.5:1。'
  if(contrast(theme.sidebarText,theme.sidebar)<4.5)return '侧栏文字与背景的对比度须达到 4.5:1，请调整侧栏颜色。'
  if(contrast(theme.accent,theme.surface)<3)return '强调色与面板的对比度须达到 3:1。'
  if([theme.success,theme.warning,theme.error].some(c=>contrast(c,theme.surface)<3))return '状态色与面板的对比度须达到 3:1。'
  return ''
}
function paint(theme:ClientTheme){
  const root=document.documentElement,style=root.style
  const ink=contrast('#F0F3F8',theme.accent)>=contrast('#101318',theme.accent)?'#F0F3F8':'#101318'
  const values:Record<string,string>={...theme,'sidebar-text':theme.sidebarText,'accent-ink':ink,tint:theme.selected,'control-selected':theme.selected}
  for(const [key,value] of Object.entries(values))style.setProperty('--client-'+key,value)
  style.setProperty('--client-glass-chrome',readableCoverage(theme.sidebar,theme.sidebarText,85)+'%')
  style.setProperty('--client-glass-panel',readableCoverage(theme.surface,theme.secondary,85)+'%')
  root.dataset.clientTheme='custom';style.colorScheme=luminance(theme.surface)<.18?'dark':'light'
  if(window.ClashAndroid)void androidRequest('/api/android/theme','POST',{background:theme.background,dark:style.colorScheme==='dark'}).catch(()=>{})
}
export function saveTheme(theme:ClientTheme){const error=themeError(theme);if(error)throw new Error(error);localStorage.setItem(storageKey,JSON.stringify(theme));localStorage.setItem(modeKey,'custom');currentTheme.value={...theme};themeMode.value='custom';refreshTheme()}
function refreshTheme(){paint(effectiveTheme());themeEpoch.value++}
export function setThemeMode(mode:Exclude<ThemeMode,'custom'>){
  themeMode.value=mode
  try{localStorage.setItem(modeKey,mode)}catch{/* storage full: keep the choice for this session */}
  try{localStorage.removeItem(storageKey)}catch{/* keep the palette only in memory */}
  currentTheme.value={...defaultTheme}
  refreshTheme()
}
export function setBackgroundPalette(dark:boolean|null){automatic=dark;refreshTheme()}
export function resetTheme(){try{localStorage.removeItem(storageKey)}catch{};currentTheme.value={...defaultTheme};setThemeMode('system')}
export function initializeTheme(){
  try{softBackground.value=localStorage.getItem('clash-studio-soft-background-v1')!=='false'}catch{softBackground.value=true}
  document.documentElement.dataset.softBackground=softBackground.value?'on':'off'
  themeMode.value=restoreMode()
  window.addEventListener('clash-android-system-theme',()=>{if(typeof window.__clashAndroidSystemDark==='boolean'){systemDark.value=window.__clashAndroidSystemDark;refreshTheme()}})
  if(typeof matchMedia==='function'){
    systemDark.value=window.__clashAndroidSystemDark??matchMedia('(prefers-color-scheme: dark)').matches
    const query=matchMedia('(prefers-color-scheme: dark)')
    const onChange=(event:MediaQueryListEvent)=>{systemDark.value=window.__clashAndroidSystemDark??event.matches;refreshTheme()}
    // Older Android WebViews only expose addListener.
    if(typeof query.addEventListener==='function')query.addEventListener('change',onChange)
    else if(typeof (query as MediaQueryList & {addListener?:unknown}).addListener==='function')(query as MediaQueryList & {addListener:(listener:(event:MediaQueryListEvent)=>void)=>void}).addListener(onChange)
  }
  try{
    const saved=JSON.parse(localStorage.getItem(storageKey)||'null')
    const legacy=['accent','background','surface','text','sidebar','sidebarText'] as const
    if(saved&&legacy.every(key=>validHex(saved[key]))){
      const base=luminance(saved.surface)<.18?darkTheme:lightTheme
      const theme={...base,...Object.fromEntries(themeFields.filter(f=>validHex(saved[f.key])).map(f=>[f.key,saved[f.key]]))} as ClientTheme
      if(!themeError(theme))currentTheme.value=theme
      else if(!('secondary' in saved)){theme.secondary=theme.text;theme.selected=theme.surface;theme.accent=contrast(theme.accent,theme.surface)>=3?theme.accent:base.accent;if(!themeError(theme))currentTheme.value=theme}
    }
  }catch{/* Invalid storage uses the default dark palette. */}
  refreshTheme()
}
