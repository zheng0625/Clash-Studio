import { ref } from 'vue'

export type ClientTheme={accent:string;background:string;surface:string;text:string;sidebar:string;sidebarText:string}
export const defaultTheme:ClientTheme={accent:'#6445b4',background:'#f7f8fc',surface:'#ffffff',text:'#3d3550',sidebar:'#242236',sidebarText:'#e6dff5'}
export const themeFields:{key:keyof ClientTheme;label:string}[]=[
  {key:'accent',label:'主色'},{key:'background',label:'页面背景'},{key:'surface',label:'卡片背景'},
  {key:'text',label:'正文文字'},{key:'sidebar',label:'侧栏与标题栏'},{key:'sidebarText',label:'侧栏文字'},
]
export const themePresets=[
  {name:'经典紫',colors:defaultTheme},
  {name:'雾蓝',colors:{accent:'#3565a0',background:'#f1f5fa',surface:'#ffffff',text:'#243247',sidebar:'#172438',sidebarText:'#e4ecf7'}},
  {name:'松林绿',colors:{accent:'#26735a',background:'#f3f6f2',surface:'#ffffff',text:'#263a30',sidebar:'#15291f',sidebarText:'#e1ede4'}},
  {name:'暖砂',colors:{accent:'#8b6140',background:'#f6f2eb',surface:'#fffdf8',text:'#40372f',sidebar:'#302820',sidebarText:'#f2e8d9'}},
  {name:'深夜',colors:{accent:'#9abcf7',background:'#12151b',surface:'#1c222c',text:'#e3e8f0',sidebar:'#0d1016',sidebarText:'#dce4f0'}},
]
const storageKey='clash-studio-client-theme-v1'
export const currentTheme=ref<ClientTheme>({...defaultTheme})
let custom=false,automatic:boolean|null=null
export function validHex(value:unknown):value is string{return typeof value==='string'&&/^#[0-9a-f]{6}$/i.test(value)}
function rgb(hex:string){return [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16))}
function luminance(hex:string){const c=rgb(hex).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return .2126*c[0]!+.7152*c[1]!+.0722*c[2]!}
export function contrast(a:string,b:string){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)}
function mix(a:string,b:string,t:number){const x=rgb(a),y=rgb(b);return '#'+x.map((v,i)=>Math.round(v+(y[i]!-v)*t).toString(16).padStart(2,'0')).join('')}
export function readableCoverage(surface:string,text:string,requested:number){for(let p=Math.ceil(requested);p<=100;p++){if(contrast(text,mix(surface,'#000000',1-p/100))>=4.5&&contrast(text,mix(surface,'#ffffff',1-p/100))>=4.5)return p}return 100}
export function effectiveTheme(){if(automatic!==null){const base=automatic?themePresets.find(p=>p.name==='深夜')!.colors:defaultTheme;return {...base,accent:currentTheme.value.accent}}return currentTheme.value}
export function secondaryColor(theme:ClientTheme,photoAutomatic=automatic!==null){for(let n=photoAutomatic?18:34;n>=0;n--){const c=mix(theme.text,theme.surface,n/100);if(contrast(c,theme.surface)>=4.5&&contrast(c,theme.background)>=4.5)return c}return theme.text}
export function themeError(theme:ClientTheme){
  if(!themeFields.every(f=>validHex(theme[f.key])))return '请输入有效的六位十六进制颜色，例如 #7659d5。'
  if(contrast(theme.text,theme.surface)<4.5||contrast(theme.text,theme.background)<4.5)return '正文与卡片、页面背景的对比度须达到 4.5:1，请调整文字或背景。'
  if(contrast(theme.sidebarText,theme.sidebar)<4.5)return '侧栏文字与背景的对比度须达到 4.5:1，请调整侧栏颜色。'
  return ''
}
function paint(theme:ClientTheme){
  const root=document.documentElement, style=root.style
  const secondary=secondaryColor(theme)
  const ink=contrast('#ffffff',theme.accent)>=contrast('#111111',theme.accent)?'#ffffff':'#111111'
  const tinted=mix(theme.surface,theme.accent,.10)
  const selected=contrast(theme.text,tinted)>=4.5?tinted:theme.surface
  const values:Record<string,string>={accent:theme.accent,background:theme.background,surface:theme.surface,text:theme.text,secondary,sidebar:theme.sidebar,'sidebar-text':theme.sidebarText,'accent-ink':ink,tint:selected,'control-selected':selected,border:mix(theme.surface,theme.text,.22)}
  for(const [key,value] of Object.entries(values))style.setProperty('--client-'+key,value)
  root.dataset.clientTheme='custom';style.colorScheme=luminance(theme.surface)<.18?'dark':'light'
}
export function saveTheme(theme:ClientTheme){
  const error=themeError(theme);if(error)throw new Error(error)
  localStorage.setItem(storageKey,JSON.stringify(theme));currentTheme.value={...theme};custom=true;refreshTheme()
}
function refreshTheme(){
  if(automatic!==null){paint(effectiveTheme());return}
  if(custom){paint(currentTheme.value);return}
  const root=document.documentElement
  for(const key of ['accent','background','surface','text','secondary','sidebar','sidebar-text','accent-ink','tint','control-selected','border'])root.style.removeProperty('--client-'+key)
  delete root.dataset.clientTheme;root.style.removeProperty('color-scheme')
}
export function setBackgroundPalette(dark:boolean|null){automatic=dark;refreshTheme()}
export function resetTheme(){localStorage.removeItem(storageKey);custom=false;currentTheme.value={...defaultTheme};refreshTheme()}
export function initializeTheme(){
  try{const saved:unknown=JSON.parse(localStorage.getItem(storageKey)||'null');if(saved&&typeof saved==='object'&&themeFields.every(f=>validHex((saved as Record<string,unknown>)[f.key]))){const theme=Object.fromEntries(themeFields.map(f=>[f.key,(saved as ClientTheme)[f.key]])) as ClientTheme;if(!themeError(theme)){currentTheme.value={...theme};custom=true;refreshTheme()}}}catch{/* Invalid or unavailable storage keeps the default interface readable. */}
}
