export {}
const previewToolbar=document.querySelector<HTMLElement>('#toolbar')!
const canvas=document.querySelector<HTMLElement>('.canvas')!
const previewScreen=document.querySelector<HTMLElement>('.screen')!
const frame=document.querySelector<HTMLIFrameElement>('iframe')!
const selector=document.querySelector<HTMLSelectElement>('#size')!
const fit=document.querySelector<HTMLButtonElement>('#fit')!
const scaleLabel=document.querySelector<HTMLElement>('#scale')!
const emptyPreview=new URLSearchParams(location.search).get('empty')==='1'
if(emptyPreview){frame.src=frame.getAttribute('src')+'&empty=1';const freeLink=document.querySelector<HTMLAnchorElement>('header a');if(freeLink)freeLink.href+='&empty=1'}
let fitEnabled=true
function layout(){
  document.documentElement.style.setProperty('--toolbar-height',`${previewToolbar.offsetHeight}px`)
  const [width,height]=selector.value.split('x').map(Number)
  const padding=innerWidth<=650?32:48
  const ratio=fitEnabled?Math.min(1,Math.max(.1,(canvas.clientWidth-padding)/width),Math.max(.1,(canvas.clientHeight-padding)/height)):1
  // Keep the iframe's actual viewport at the requested logical size. Only
  // scale its presentation, so breakpoints match the desktop WebView.
  frame.style.width=`${width}px`;frame.style.height=`${height}px`
  frame.style.transform=`scale(${ratio})`
  previewScreen.style.width=`${width*ratio+2}px`;previewScreen.style.height=`${height*ratio+2}px`
  scaleLabel.textContent=`${Math.round(ratio*100)}%`
}
selector.addEventListener('change',layout)
fit.addEventListener('click',()=>{fitEnabled=!fitEnabled;fit.setAttribute('aria-pressed',String(fitEnabled));fit.textContent=fitEnabled?'缩放适应':'实际大小';layout()})
new ResizeObserver(layout).observe(previewToolbar)
window.addEventListener('resize',layout)
layout()
