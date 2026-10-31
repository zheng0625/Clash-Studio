<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronRight, RefreshCw } from 'lucide-vue-next'
import { t } from './i18n'

type Proxy={name:string;type:string;all?:string[];now?:string}
const props=defineProps<{profiles:{id:string;title:string}[];selected:string;proxies:Record<string,Proxy>;busy:boolean;loading:boolean;live:boolean;running:boolean;mode:string|null|undefined;status:string;error:string;hasProviders:boolean}>()
const emit=defineEmits<{choose:[id:string];select:[group:Proxy,name:string];retry:[];proxies:[]}>()
const groupName=ref('')
const groups=computed(()=>Object.values(props.proxies).filter(p=>p.all&&(props.mode==='global'&&props.live?p.name==='GLOBAL':p.name!=='GLOBAL')))
watch(()=>props.selected,()=>groupName.value='',{flush:'sync'})
watch(groups,value=>{if(!value.some(p=>p.name===groupName.value))groupName.value=(value.find(p=>p.type==='Selector')||value[0])?.name||''},{immediate:true,flush:'sync'})
const group=computed(()=>groups.value.find(p=>p.name===groupName.value))
const members=computed(()=>group.value?.all||[])
const value=computed(()=>group.value?.now||'')
const nodeDisabled=computed(()=>props.busy||props.loading||!!props.error||props.mode==='direct'||group.value?.type!=='Selector'||!members.value.length)
function chooseNode(event:Event){if(group.value&&!nodeDisabled.value)emit('select',group.value,(event.target as HTMLSelectElement).value)}
</script>

<template>
  <section class="desk-card overview-selection">
    <div class="section-head"><h2>{{ t('方案选择') }}</h2><span v-if="status" class="selection-state" role="status">{{ status }}</span><span v-else class="selection-state">{{ !running?t('下次启动使用'):!live?t('待应用'):t('快捷切换') }}</span></div>
    <label class="overview-select-row"><span>{{ t('方案') }}</span><select :value="selected" :disabled="busy" :aria-label="t('方案')" @change="emit('choose',($event.target as HTMLSelectElement).value)"><option v-if="!profiles.length" value="">{{ t('先导入订阅') }}</option><option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.title }}</option></select></label>
    <label class="overview-select-row"><span>{{ t('策略组') }}</span><select v-model="groupName" :disabled="busy||loading||!!error||!groups.length||mode==='direct'" :aria-label="t('策略组')"><option v-if="!groups.length" value="">{{ loading?t('正在加载…'):t('暂无策略组') }}</option><option v-for="g in groups" :key="g.name" :value="g.name">{{ g.name }}</option></select></label>
    <label class="overview-select-row"><span>{{ t('节点') }}</span><select :value="value" :disabled="nodeDisabled" :aria-label="t('节点')" @change="chooseNode"><option v-if="!value" value="">{{ mode==='direct'?t('不使用代理节点'):loading?t('正在加载…'):t('请选择节点') }}</option><option v-if="value&&!members.includes(value)" :value="value">{{ value }}</option><option v-for="name in members" :key="name" :value="name">{{ name }}{{ proxies[name]?.all?' · '+t('策略组'):'' }}</option></select></label>
    <p v-if="error" class="overview-select-note error" role="alert">{{ error }} <button class="desk-text-btn" :disabled="loading||busy" @click="emit('retry')"><RefreshCw :size="13"/>{{ t('重试') }}</button></p>
    <p v-else-if="mode==='direct'" class="overview-select-note">{{ t('直连模式下不使用代理节点') }}</p>
    <p v-else-if="group&&group.type!=='Selector'" class="overview-select-note">{{ t('自动策略组由内核选择节点') }}</p>
    <button v-if="hasProviders||(!groups.length&&selected&&!loading&&!error)" class="desk-text-btn overview-catalog-link" @click="emit('proxies')">{{ t('前往代理页管理节点') }}<ChevronRight :size="13"/></button>
  </section>
</template>
