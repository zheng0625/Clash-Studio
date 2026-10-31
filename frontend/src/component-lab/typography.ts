export const typographyKeys=['font-size','font-weight','font-family','line-height','letter-spacing','text-align','white-space','word-break','text-indent','writing-mode'] as const
export type TypographyKey=typeof typographyKeys[number]
export type Typography=Record<TypographyKey,string>
const choices:Partial<Record<TypographyKey,readonly string[]>>={
 'font-weight':['normal','bold','100','200','300','400','500','600','700','800','900'],
 'font-family':['inherit','system-ui, sans-serif','sans-serif','serif','monospace'],
 'text-align':['start','left','center','right','end','justify'],
 'white-space':['normal','nowrap','pre-wrap','pre-line','break-spaces'],
 'word-break':['normal','break-all','keep-all'],
 'writing-mode':['horizontal-tb','vertical-rl','vertical-lr'],
}
export function validTypography(key:string,value:string):boolean{
 if(!(typographyKeys as readonly string[]).includes(key))return false
 const allowed=choices[key as TypographyKey];if(allowed)return allowed.includes(value)
 if(['line-height','letter-spacing'].includes(key)&&value==='normal')return true
 if(!/^-?(?:\d+(?:\.\d+)?|\.\d+)px$/.test(value))return false
 const number=parseFloat(value)
 return key==='font-size'?number>=1&&number<=240:key==='line-height'?number>=1&&number<=600:key==='letter-spacing'?number>=-20&&number<=100:key==='text-indent'?Math.abs(number)<=1000:false
}
