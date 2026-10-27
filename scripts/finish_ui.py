from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/'frontend/src/Client.vue'
source=path.read_text(encoding='utf-8')
old='<button class="desk-btn primary" @click="importOpen=true"><Plus :size="16"/>导入订阅</button>'
replacement='<button class="desk-btn" :disabled="!!busy||editorDirty||!selected" @click="apply"><Power :size="15"/>应用配置</button>'+old
assert old in source
source=source.replace(old,replacement,1)
path.write_text(source,encoding='utf-8')
path=root/'frontend/index.html'
source=path.read_text(encoding='utf-8').replace('Clash Studio · Windows Alpha','Clash Studio')
path.write_text(source,encoding='utf-8')
