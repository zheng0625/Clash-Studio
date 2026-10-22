import { createApp } from 'vue'
import BootApp from './BootApp.vue'
import './verge.css'
import './native-editor.css'
import './polish.css'
import './release03.css'
import './release04.css'
import './a11y-tokens.css'
import './client-theme.css'
import { initializeTheme } from './theme'
import { initializeBackground } from './background'
import { initializeLanguage } from './i18n'
initializeTheme()
void initializeBackground()
void initializeLanguage()
createApp(BootApp).mount('#app')
