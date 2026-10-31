import { createApp } from 'vue'
import '../client-styles'
import Lab from './Lab.vue'
import './lab.css'

document.documentElement.classList.add('component-workshop')
createApp(Lab).mount('#app')
