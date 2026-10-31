import { createApp } from 'vue'
import Proposal from './Proposal.vue'
import './proposal.css'

// A standalone design preview: no desktop bridge, backend, or application storage.
createApp(Proposal).mount('#app')
