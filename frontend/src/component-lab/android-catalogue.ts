import { catalogue as desktopCatalogue, type CatalogueEntry, type PreviewStep } from './catalogue'
const excluded=new Set(['modules','memory','shell-topbar','shell-dock','select','pagination','settings-behavior','proxy-delay'])
const names:Record<string,string>={home:'概览',subscriptions:'订阅',proxies:'代理',connections:'连接诊断',routing:'精确分流',settings:'设置与日志'}
function block(id:string,name:string,page:string,selector:string,source:string,steps:PreviewStep[]=[]):CatalogueEntry{return {id,name,page,selector,source,steps,states:['正常'],group:names[page]||'公共框架',hint:'安卓正式页面原位预览：'+name+'。支持选择内部元素、调整尺寸及中心坐标。'}}
export const androidCatalogue:CatalogueEntry[]=[
 ...desktopCatalogue.filter(e=>['home','subscriptions','proxies','connections','settings'].includes(e.page)&&!excluded.has(e.id)).map(e=>({...e,group:names[e.page],states:e.id==='kernel'?['待启动','运行中','应用中','待应用','应用失败','未导入','全局模式','直连模式']:e.id==='settings-language'?['正常','英文']:e.states,hint:'安卓原位 · '+e.hint})),
 {...block('android-navigation','安卓底部导航','home','.mobile-navigation','Client.vue'),group:'公共框架'},
 {...block('android-heading','移动页面标题','home','.desk-page-heading','Client.vue'),group:'公共框架'},
 block('android-delay','浮动测速按钮','proxies','.delay-fab','ProxyPanel.vue'),
 block('android-benchmark','节点延迟测速面板','proxies','.delay-toolbar','ProxyPanel.vue',[{selector:'.delay-fab'}]),
 {...block('routing-list','精确分流规则列表','routing','.android-routing','AndroidRouting.vue'),states:['正常','空列表','加载中','读取失败','大量规则']},
 block('routing-pagination','规则分页与每页条数','routing','.routing-page-size','AndroidRouting.vue'),
 block('routing-filters','规则搜索与筛选','routing','.routing-filters','AndroidRouting.vue'),
 block('routing-row','规则条目与排序按钮','routing','.routing-summary','AndroidRouting.vue'),
 block('routing-save','规则保存与应用栏','routing','.routing-save-bar','AndroidRouting.vue'),
 block('routing-create','添加规则弹窗','routing','dialog[open].routing-editor','AndroidRouting.vue',[{selector:'.android-routing .section-head button'}]),
 block('routing-edit','编辑规则与应用选择','routing','dialog[open].routing-editor','AndroidRouting.vue',[{selector:'.routing-summary-main'}]),
 block('android-permissions','相机、通知与 VPN 权限','settings','.android-permissions','AndroidPermissions.vue'),
 block('android-qr','二维码订阅导入','subscriptions','.qr-import-options','Client.vue',[{selector:'.heading-buttons button',text:'导入订阅'},{selector:'.import-method-tabs button',text:'二维码订阅'}]),
 block('android-file','YAML 文件导入','subscriptions','.file-import','Client.vue',[{selector:'.heading-buttons button',text:'导入订阅'},{selector:'.import-method-tabs button',text:'YAML 文件'}]),
]
