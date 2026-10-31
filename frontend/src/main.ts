import { createApp } from 'vue'
import './client-styles'
import BootApp from './BootApp.vue'
import TrayMenu from './TrayMenu.vue'
import './mobile-tier'
import { initializeTheme } from './theme'
import { initializeBackground } from './background'
import { initializeLanguage } from './i18n'
const tray=new URLSearchParams(location.search).has('tray')
if(tray)document.documentElement.classList.add('tray-surface')
else{initializeTheme();void initializeBackground()}
void initializeLanguage()
createApp(tray?TrayMenu:BootApp).mount('#app')
