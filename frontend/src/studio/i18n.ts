import { computed, ref, watch } from 'vue'
import english from './locales/en.json'

export type Language = 'auto' | 'zh-CN' | 'en'
const key = 'clash-studio-language-v1'
function saved(): Language { try {const v=localStorage.getItem(key);return v==='en'||v==='zh-CN'?v:'auto'}catch{return 'auto'} }
export const language = ref<Language>(saved())
const browserLanguage=ref(navigator.languages?.[0]||navigator.language||'en')
export const locale=computed(() => language.value==='auto'?(browserLanguage.value.toLowerCase().startsWith('zh')?'zh-CN':'en'):language.value)
const catalogue:Record<string,string>=english
const patterns=Object.entries(catalogue).filter(([source])=>/\{\d+\}/.test(source)).sort((a,b)=>b[0].length-a[0].length).map(([source,target])=>{
  const indices:number[]=[]
  const pattern=source.split(/(\{\d+\})/g).map(part=>/^\{\d+\}$/.test(part)?(indices.push(Number(part.slice(1,-1))),'([\\s\\S]*?)'):part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('')
  return {regex:new RegExp('^'+pattern+'$'),target,indices}
})
const format=(value:string,args:unknown[])=>value.replace(/\{(\d+)\}/g,(whole,index)=>args[Number(index)]===undefined?whole:String(args[Number(index)]))
export function t(source:string,args:unknown[]=[]):string {return format(locale.value==='en'?(catalogue[source]??source):source,args)}
/** Translate only application diagnostics; never apply this to user config values. */
export function message(value:string|null|undefined):string {
  const source=value||''
  if(locale.value!=='en'||!source)return source
  if(catalogue[source])return catalogue[source]
  for(const p of patterns){const match=source.match(p.regex);if(match){const args:unknown[]=[];p.indices.forEach((index,i)=>{args[index]=match[i+1]});return format(p.target,args)}}
  if(source.includes('；'))return source.split('；').map(message).join('; ')
  const prefix='更新产生冲突，继续提供上一份可用配置。'
  if(source.startsWith(prefix))return t(prefix)+message(source.slice(prefix.length))
  return source
}
window.addEventListener('languagechange',()=>{browserLanguage.value=navigator.languages?.[0]||navigator.language||'en'})
window.addEventListener('storage',event=>{if(event.key===key)language.value=saved()})
watch(language,value=>{try{localStorage.setItem(key,value)}catch{}},{flush:'sync'})
watch(locale,value=>{document.documentElement.lang=value;document.title=value==='en'?'Clash Studio · Subscription Workspace':'Clash Studio · 订阅工作台'},{immediate:true})
