import { ref, watch } from 'vue'
import { setBackgroundPalette, readableCoverage, effectiveTheme, secondaryColor, currentTheme } from './theme'
export type Crop={x:number;y:number;width:number;height:number}
export type Wallpaper={blob:Blob;rendered?:Blob;name:string;shade:number;blur?:number;panel?:number;adapt?:boolean;dark?:boolean;crop?:Crop;ratio?:string}
export const backgroundState=ref({name:'',shade:45,blur:0,panel:92,adapt:false,hasImage:false})
export const backgroundUrl=ref('')
let revision=0
function database():Promise<IDBDatabase>{return new Promise((resolve,reject)=>{const request=indexedDB.open('clash-studio-appearance-v1',1);request.onupgradeneeded=()=>request.result.createObjectStore('settings');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(new Error('无法打开本机图片存储'))})}
async function storage(action:'get'|'put'|'delete',value?:Wallpaper):Promise<Wallpaper|undefined>{
  const db=await database()
  try{return await new Promise((resolve,reject)=>{const transaction=db.transaction('settings',action==='get'?'readonly':'readwrite'),store=transaction.objectStore('settings');const request=action==='get'?store.get('background'):action==='put'?store.put(value,'background'):store.delete('background');transaction.oncomplete=()=>resolve(action==='get'?request.result:undefined);transaction.onerror=()=>reject(new Error('图片保存失败，请检查磁盘空间'));transaction.onabort=()=>reject(new Error('图片存储已取消'))})}finally{db.close()}
}
const clamp=(v:number,min:number,max:number)=>Math.max(min,Math.min(max,Number.isFinite(v)?v:min))
function protectText(panel:number){const palette=effectiveTheme(),style=document.documentElement.style;const coverage=Math.max(readableCoverage(palette.surface,palette.text,panel),readableCoverage(palette.surface,secondaryColor(palette),panel));style.setProperty('--wallpaper-panel',coverage+'%');style.setProperty('--wallpaper-chrome',readableCoverage(palette.sidebar,palette.sidebarText,Math.max(80,panel-8))+'%')}
watch(currentTheme,()=>{if(backgroundState.value.hasImage)protectText(backgroundState.value.panel)},{flush:'sync'})
function apply(value?:Wallpaper){
  const previous=backgroundUrl.value,style=document.documentElement.style
  backgroundUrl.value=value?URL.createObjectURL(value.rendered??value.blob):''
  if(value){
    style.setProperty('--wallpaper-image',`url("${backgroundUrl.value}")`)
    style.setProperty('--wallpaper-shade',`${clamp(value.shade,0,90)}%`)
    style.setProperty('--wallpaper-blur',`${clamp(value.blur??0,0,20)}px`)
    style.setProperty('--wallpaper-panel',`${clamp(value.panel??92,75,100)}%`)
    style.setProperty('--wallpaper-chrome',`${Math.max(80,clamp(value.panel??92,75,100)-8)}%`)
    document.documentElement.dataset.wallpaper='on'
    setBackgroundPalette(value.adapt?!!value.dark:null)
    protectText(clamp(value.panel??92,75,100))
  }else{
    for(const name of ['image','shade','blur','panel','chrome'])style.removeProperty('--wallpaper-'+name)
    delete document.documentElement.dataset.wallpaper;setBackgroundPalette(null)
  }
  backgroundState.value=value?{name:value.name,shade:value.shade,blur:value.blur??0,panel:value.panel??92,adapt:!!value.adapt,hasImage:true}:{name:'',shade:45,blur:0,panel:92,adapt:false,hasImage:false}
  if(previous)URL.revokeObjectURL(previous)
}
export async function readBackground(){return storage('get')}
export async function initializeBackground(){const start=revision;try{const value=await readBackground();if(start===revision&&value?.blob instanceof Blob&&value.blob.type==='image/webp'&&value.blob.size<=6*1024*1024&&Number.isFinite(value.shade))apply(value)}catch{/* A broken image record must not prevent startup. */}}
function webp(canvas:HTMLCanvasElement){return new Promise<Blob>((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('图片处理失败')),'image/webp',.9))}
export async function preparePhoto(file:File){
  if(file.size>15*1024*1024)throw new Error('图片不能超过 15 MB')
  const signature=Array.from(new Uint8Array(await file.slice(0,12).arrayBuffer())).map(n=>n.toString(16).padStart(2,'0')).join('')
  if(!signature.startsWith('ffd8ff')&&!signature.startsWith('89504e470d0a1a0a')&&!(signature.startsWith('52494646')&&signature.slice(16)==='57454250'))throw new Error('请选择 JPEG、PNG 或 WebP 照片')
  const image=await createImageBitmap(file)
  try{
    if(image.width*image.height>40_000_000)throw new Error('照片不能超过 4000 万像素')
    const factor=Math.min(1,2560/image.width,2560/image.height),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.width*factor));canvas.height=Math.max(1,Math.round(image.height*factor));const context=canvas.getContext('2d');if(!context)throw new Error('无法处理照片');context.drawImage(image,0,0,canvas.width,canvas.height)
    const blob=await webp(canvas)
    if(blob.size>6*1024*1024)throw new Error('照片处理后仍然过大')
    return blob
  }finally{image.close()}
}
export async function photoInfo(blob:Blob){
  const image=await createImageBitmap(blob)
  try{const canvas=document.createElement('canvas');canvas.width=canvas.height=24;const context=canvas.getContext('2d')!;context.drawImage(image,0,0,24,24);const data=context.getImageData(0,0,24,24).data;let total=0;for(let i=0;i<data.length;i+=4)total+=(data[i]!*.2126+data[i+1]!*.7152+data[i+2]!*.0722)/255;return {width:image.width,height:image.height,dark:total/(24*24)<.48}}finally{image.close()}
}
export async function saveBackground(value:Wallpaper){
  ++revision
  const image=await createImageBitmap(value.blob)
  try{
    const crop=value.crop??{x:0,y:0,width:1,height:1}
    if(!Object.values(crop).every(Number.isFinite)||crop.x<0||crop.y<0||crop.width<=0||crop.height<=0||crop.x+crop.width>1.001||crop.y+crop.height>1.001)throw new Error('裁切范围无效，请重置裁切')
    const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.width*crop.width));canvas.height=Math.max(1,Math.round(image.height*crop.height));const context=canvas.getContext('2d');if(!context)throw new Error('无法裁切照片');context.drawImage(image,crop.x*image.width,crop.y*image.height,crop.width*image.width,crop.height*image.height,0,0,canvas.width,canvas.height)
    const rendered=await webp(canvas),result={...value,rendered,shade:clamp(value.shade,0,90),blur:clamp(value.blur??0,0,20),panel:clamp(value.panel??92,75,100)}
    await storage('put',result);apply(result)
  }finally{image.close()}
}
export async function clearBackground(){++revision;await storage('delete');apply()}
