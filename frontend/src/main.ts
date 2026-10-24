import { createApp } from 'vue'
import BootApp from './BootApp.vue'
import TrayMenu from './TrayMenu.vue'
import './verge.css'
import './native-editor.css'
import './polish.css'
import './release03.css'
import './release04.css'
import './a11y-tokens.css'
import './client-theme.css'
import './liquid-glass.css'
import './settings-layout.css'
import './semantic-theme.css'
import { initializeTheme } from './theme'
import { initializeBackground } from './background'
import { initializeLanguage } from './i18n'
const tray=new URLSearchParams(location.search).has('tray')
if(tray)document.documentElement.classList.add('tray-surface')
else{initializeTheme();void initializeBackground()}
void initializeLanguage()
createApp(tray?TrayMenu:BootApp).mount('#app')
