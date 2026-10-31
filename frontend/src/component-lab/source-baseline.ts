// Bump only when deliberately adopting a new tested source layout on both platforms.
export const sourceBaseline='20261031-latest-test-v1'
export function adoptSourceBaseline(storage:Storage,key:string){
  const marker=key+'-source-baseline'
  if(storage.getItem(marker)===sourceBaseline)return
  const existing=storage.getItem(key)
  if(existing&&existing!=='[]')storage.setItem(key+'-before-'+sourceBaseline,existing)
  storage.setItem(key,'[]')
  storage.setItem(marker,sourceBaseline)
}
