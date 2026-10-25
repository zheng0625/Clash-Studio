<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { ArrowDown, ArrowUp, Plus, Save, Trash2 } from 'lucide-vue-next'
import { api } from './api'
import { t, message } from './i18n'
import GlassSelect from './GlassSelect.vue'
type Rule={kind:string;value:string;target:string;enabled:boolean}
type State={revision:number;rules:Rule[];targets:string[]}
const props=defineProps<{profileId:string}>()
const emit=defineEmits<{changed:[];dirty:[value:boolean]}>()
const rules=ref<Rule[]>([]), targets=ref<string[]>([]), revision=ref(0), busy=ref(false), error=ref(''), saved=ref(''), dirty=ref(false)
const apps=ref<{package:string;label:string}[]>([])
api<{package:string;label:string}[]>('/api/android/apps').then(value=>{apps.value=value.sort((a,b)=>a.label.localeCompare(b.label))}).catch(()=>{})
const kinds=[{value:'DOMAIN-SUFFIX',label:t('域名后缀')},{value:'DOMAIN',label:t('精确域名')},{value:'IP-CIDR',label:t('IPv4 网段')},{value:'IP-CIDR6',label:t('IPv6 网段')},{value:'PROCESS-NAME',label:t('应用包名')}]
let request=0
function changed(){dirty.value=true;saved.value='';emit('dirty',true)}
async function load(){const sequence=++request;error.value='';rules.value=[];targets.value=[];dirty.value=false;emit('dirty',false);if(!props.profileId)return;busy.value=true;try{const r=await api<State>('/api/android/routing?profile_id='+encodeURIComponent(props.profileId));if(sequence!==request)return;rules.value=r.rules;targets.value=r.targets;revision.value=r.revision}catch(e){if(sequence===request)error.value=(e as Error).message}finally{if(sequence===request)busy.value=false}}
function add(){rules.value.push({kind:'DOMAIN-SUFFIX',value:'',target:'DIRECT',enabled:true});changed()}
function move(index:number,offset:number){const j=index+offset;if(j<0||j>=rules.value.length)return;[rules.value[index],rules.value[j]]=[rules.value[j]!,rules.value[index]!];changed()}
async function save(){busy.value=true;error.value='';saved.value='';try{const r=await api<State>('/api/android/routing','PUT',{profile_id:props.profileId,revision:revision.value,rules:rules.value});rules.value=r.rules;targets.value=r.targets;revision.value=r.revision;dirty.value=false;emit('dirty',false);saved.value=t('规则已保存，应用配置后生效。');emit('changed')}catch(e){error.value=(e as Error).message}finally{busy.value=false}}
watch(()=>props.profileId,load,{immediate:true});onUnmounted(()=>{++request;emit('dirty',false)})
</script>
<template>
 <section class="desk-card android-routing">
  <div class="section-head"><h2>{{ t('精确分流') }}</h2><button class="desk-btn" :disabled="busy||!profileId||rules.length>=500" @click="add"><Plus :size="16"/>{{ t('添加规则') }}</button></div>
  <p class="page-caption">{{ t('规则从上到下优先匹配，位于订阅规则之前；仅在规则模式下生效。保存后点击应用配置。') }}</p>
  <p v-if="!profileId" class="desk-empty">{{ t('请先选择一份订阅。') }}</p>
  <p v-else-if="!rules.length&&!busy" class="desk-empty">{{ t('尚无自定义规则，当前使用订阅原有分流。') }}</p>
  <form v-if="profileId" @submit.prevent="save">
   <fieldset v-for="(rule,index) in rules" :key="index" :disabled="busy" class="routing-rule">
    <legend>{{ t('规则 {0}',[index+1]) }}</legend>
    <label class="desk-field">{{ t('匹配类型') }}<GlassSelect v-model="rule.kind" :options="kinds" :label="t('匹配类型')" @update:model-value="changed"/></label>
    <label class="desk-field">{{ t('匹配值') }}<input v-model="rule.value" required maxlength="253" :placeholder="rule.kind==='PROCESS-NAME'?'com.android.chrome':rule.kind.startsWith('IP-')?'192.168.1.0/24':'example.com'" autocomplete="off" @input="changed"/></label>
    <label v-if="rule.kind==='PROCESS-NAME'&&apps.length" class="desk-field">{{ t('从已安装应用选择') }}<GlassSelect v-model="rule.value" :options="apps.map(app=>({value:app.package,label:app.label+' · '+app.package}))" :label="t('从已安装应用选择')" @update:model-value="changed"/></label>
    <label class="desk-field">{{ t('目标出口') }}<GlassSelect v-model="rule.target" :options="targets.map(value=>({value,label:value}))" :label="t('目标出口')" @update:model-value="changed"/></label>
    <div class="routing-rule-actions"><label><input v-model="rule.enabled" type="checkbox" @change="changed"/> {{ t('启用') }}</label><button type="button" class="desk-icon-btn" :aria-label="t('上移')" :disabled="index===0" @click="move(index,-1)"><ArrowUp :size="17"/></button><button type="button" class="desk-icon-btn" :aria-label="t('下移')" :disabled="index===rules.length-1" @click="move(index,1)"><ArrowDown :size="17"/></button><button type="button" class="desk-icon-btn danger" :aria-label="t('删除规则')" @click="rules.splice(index,1);changed()"><Trash2 :size="17"/></button></div>
   </fieldset>
   <p v-if="error" class="desk-alert error" role="alert">{{ message(error) }}</p><p v-if="saved" role="status">{{ saved }}</p>
   <button class="desk-btn primary" :disabled="busy||!dirty"><Save :size="16"/>{{ busy?t('正在保存…'):t('保存规则') }}</button>
  </form>
 </section>
</template>
<style scoped>
.android-routing{padding:20px}.android-routing>.page-caption{line-height:1.8;margin:14px 0}.routing-rule{min-width:0;display:grid;grid-template-columns:1fr;gap:14px;padding:16px;margin:18px 0;border:1px solid var(--client-border);border-radius:16px}.routing-rule legend{padding:0 7px;font-size:13px;color:var(--client-secondary)}.routing-rule-actions{display:flex;align-items:center;gap:12px}.routing-rule-actions>label{margin-right:auto;display:flex;align-items:center;gap:8px;font-size:13px}.routing-rule-actions .desk-icon-btn{min-width:44px;min-height:44px}
</style>
