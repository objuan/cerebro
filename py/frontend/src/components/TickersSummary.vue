<template>
  <header class="py-1 mb-1 border-bottom bg-light">
 
     <div class="d-flex flex-wrap gap-2">

      <div
        v-for="item in symbolList"
        :key="item.symbol"
        class="card ticket-card"
      >
        <div class="card-body p-2 d-flex justify-content-between align-items-center">
          
         
            <div class="fw-bold">{{ item.symbol }}</div>
            <small class="text-muted">{{ item.last }}</small>
          

          <div
            class="fw-bold ms-3"
            :class="item.gain >= 0 ? 'text-success' : 'text-danger'"
          >
            {{ item.gain }}%
          </div>

        </div>
      </div>

    </div>
  </header>
</template>

<script setup>

import {  ref,onMounted, onUnmounted  } from 'vue';
//import { computed } from 'vue';
//import { liveStore } from '@/components/liveStore.js'; // Assicurati che il percorso sia corretto
import { send_get } from '@/components/utils.js'; // Usa il percorso corretto

const symbolList = ref([]);

// Esponiamo i dati dello store al template
//const liveData = computed(() => liveStore.state.dataByPath);

defineProps({
})

onMounted( async () => {
  
  let data = await send_get("/api/symbols")
  //console.log("Symbols ",data.symbols)
  symbolList.value =[]
  data.symbols.forEach(symbol => {
    symbolList.value.push({"symbol" : symbol});
  });
 
});
onUnmounted(() => {


});

function updateSymbol(ticket){
    //console.log("updateSymbol", ticket);
    const item = symbolList.value.find(
      s => s.symbol === ticket.symbol
    );
    if (item) {
      item.last = ticket.last;
      item.gain = ticket.gain.toFixed(2);
    }
}

defineExpose({
  updateSymbol,
});


</script>

<style scoped>
.ticket-card {
  min-width: 160px;
  max-width: 250px;
}
</style>