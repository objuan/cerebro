<template>
  <header class="py-1 mb-1 border-bottom bg-light">
    <div class="container d-flex align-items-center justify-content-between">
      <h1 class="h3 mb-0 text-primary">
        <i class="bi bi-cpu-fill me-2"></i> {{ title }}
      </h1>
      <p>Ultimo aggiornamento:
         {{ liveData['root.clock'] ? formatUnixDate(liveData['root.clock']) : '...' }}
        </p>
      
      <div class="text-end">
          <span :class="['badge rounded-pill', marketStatus.color]">
          <i class="bi bi-circle-fill me-1 small"></i> {{ marketStatus.label }}
        </span>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue';
import { liveStore } from '@/components/liveStore.js'; // Assicurati che il percorso sia corretto
import { formatUnixDate } from '@/components/utils.js'; // Usa il percorso corretto

// Esponiamo i dati dello store al template
const liveData = computed(() => liveStore.state.dataByPath);

const marketStatus = computed(() => {
  const tz = liveStore.state.dataByPath['root.tz'];
  
  // Mappatura degli stati
  switch (tz) {
    case 0:
      return { label: 'Chiuso', color: 'bg-danger' };
    case 1:
      return { label: 'Pre-Market', color: 'bg-warning text-dark' };
    case 2:
      return { label: 'Aperto', color: 'bg-success' };
    case 3:
      return { label: 'After-Hours', color: 'bg-info text-dark' };
    default:
      return { label: 'Offline', color: 'bg-secondary' };
  }
});

defineProps({
  title: {
    type: String,
    default: 'Dashboard Cerebro'
  }
})
</script>

<style scoped>
/* Aggiungi qui eventuali personalizzazioni extra */
.text-primary {
  font-weight: 700;
}
</style>

<script>
import axios from 'axios';

export default {
  name: 'PageHeader',
  data() {
    return {
      msg: '',
    };
  },
  methods: {
    getMessage() {
      axios.get('/')
        .then((res) => {
          this.msg = res.data;
        })
        .catch((error) => {
          console.error(error);
        });
    },
  },
  created() {
    //this.getMessage();
  },
};
</script>