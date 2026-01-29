<template>

     <div class="d-flex flex-wrap gap-2">

     <div
      v-for="event in sortedEvents"
      :key="event.ts + event.symbol + event.name"
      class="event"
      :style="{  background: event.data.color || '#ccc' }"
    >
       <!-- HEADER -->
        <div class="event-header">
          <div class="time">
            {{ new Date(event.ts).toLocaleTimeString() }}
          </div>
          <div class="title">{{ event.name }}</div>
         
        </div>

        <!-- BODY -->
        <div class="event-body">
          
          <div class ="div-row">
            <div class="symbol fw-bold">
              <a
                href="#"
                class="text-blue-600 hover:underline"
                @click.prevent="onSymbolClick(event.symbol)"
              >
                {{ event.symbol }}
              </a>
            </div>

            <div class="msg" v-html="event.desc"></div>

            </div>
          </div>
      </div>
   
    </div>
  
</template>

<script setup>

import { computed,onMounted, onUnmounted ,onBeforeUnmount } from 'vue';

import { eventBus } from "@/components/js/eventBus";
import { eventStore as store } from "@/components/js/eventStore";


const sortedEvents = computed(() =>
  [...store.items].sort((a, b) => b.ts - a.ts)
);

/*
function formatTs(ts) {
  const d = new Date(ts);
  return d.toLocaleString();
}
  */

// Esponiamo i dati dello store al template

function onSymbolClick(symbol) {
  console.log('Symbol clicked:', symbol)
  eventBus.emit("chart-select",{"symbol" : symbol , "id": "chart_1"});
}

defineProps({
})

onMounted( async () => {
  //eventBus.on("ticker-received", onTickerReceived);
 
});

onBeforeUnmount(() => {
});

onUnmounted(() => {
});


defineExpose({
 // updateSymbol,
});

</script>

<style scoped>

.event {
  min-width: 170px;
  border: 1px solid;
  border-color: black;
  padding: 4px 5px;
  margin-bottom: 10px;
  border-radius: 6px;
  background: #ffffff;
  color:rgb(0, 0, 0);
}

.event-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  margin-bottom: 6px;
  opacity: 0.8;
}

.event-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.time {
 font-weight: 600;
 
}
.title {
  font-weight: 600;

}

.msg {
  font-size: 13px;
   flex-grow: 1;
   align-self:flex-end;
}
.div-col {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.div-row {
  display: flex;
  flex-direction: row;
  align-items: center;
}
</style>