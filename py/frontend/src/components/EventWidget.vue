<template>

     <div class="d-flex flex-wrap gap-0 justify-content-end align-content-start events-container">

       <div
          v-for="event in sortedEvents"
          :key="event.timestamp + event.symbol + event.name"
          class="event"
          :class="{ open: openKey === (event.timestamp + event.symbol + event.name) }"
          :style="{ '--event-bg': event.data.color || '#ccc' }"
          @click="toggle(event)"
        >
          <!-- HEADER -->
            <div class="event-header">
              <div class="time">
                {{ new Date(event.timestamp).toLocaleTimeString() }}
              </div>
              <div class="title">{{ event.name }}</div>
            
            </div>

            <!-- BODY -->
             <div class="div-col body">

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

                    <div class="msg" v-html="event.data.small_desc"></div>
                  </div>
           
                <!-- detail -->
                <div
                      v-if="openKey === (event.timestamp + event.symbol + event.name)"
                      class="full" >
                      <div class="div-col">
                        <div>
                            {{ event.data.full_desc }} 
                        </div>
                        <div v-if="fullDetails[event.symbol]" class="report">
                          <div class="report-item">Rank:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;{{ fullDetails[event.symbol].rank }}</div>
                          <div class="report-item">From Close: {{ fullDetails[event.symbol].gain }}%</div>
                          <div class="report-item">Gap: &nbsp;{{ fullDetails[event.symbol].gap }}%</div>
                          <div class="report-item">Volume: {{ formatValue(fullDetails[event.symbol].day_volume) }}</div>

                          <div class="report-item">Float:&nbsp;&nbsp;&nbsp; {{ formatValue(fullDetails[event.symbol].float) }}</div>
                          <div class="report-item">Rel 5: &nbsp;&nbsp;&nbsp;{{ fullDetails[event.symbol].rel_vol_24 }}</div>
                          <div class="report-item">Rel 24:&nbsp; {{ fullDetails[event.symbol].rel_vol_5m }}</div>
                          
                          
                        </div>
                      </div>
                </div>
           </div>
   </div>
    </div>
  
</template>

<script setup>

import { ref,computed,onMounted, onUnmounted ,onBeforeUnmount } from 'vue';

import { eventBus } from "@/components/js/eventBus";
import { eventStore as store } from "@/components/js/eventStore";
import { send_get } from '@/components/js/utils';
import { reportStore as report } from "@/components/js/reportStore";
import { formatValue} from "@/components/js/utils";// scaleColor

const fullDetails = {} // key -> result

const sortedEvents = computed(() =>
  [...store.items].sort((a, b) => b.timestamp - a.timestamp)
);


const openKey = ref(null)

function toggle(event) {
  const key = event.timestamp + event.symbol + event.name
  openKey.value = openKey.value === key ? null : key

  fullDetails[event.symbol] = report.get_report(event.symbol)
  console.log("fullDetails",fullDetails[event.symbol])
}


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
    let pdata = await send_get("/api/event/get")
    store.clear()
    pdata.forEach(  (val) =>{
      val.data = JSON.parse(val.data)
      store.push(val)    
    });
});

onBeforeUnmount(() => {
});

onUnmounted(() => {
});


</script>

<style scoped>

.events-container {
  height: 100%;
  overflow-y: auto;
  width: 100%;
  margin-right: 2px;
}

.event {
  width: 100%;
  max-height: 60px;
  border: 1px solid black;
  padding: 1px 1px;
  margin-bottom: 1px;
  border-radius: 6px;
  background: var(--event-bg);
  
  color:rgb(0, 0, 0);
  overflow: hidden;
  transition: all 0.25s ease;
  cursor: pointer;
}

.event.open {
  max-height: 300px; /* abbastanza per il testo */
   border: 3px solid rgb(21, 255, 0);   /* bordo bold quando selezionato */
}

.event-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  margin-bottom: 6px;
  background-color: color-mix(in srgb, var(--event-bg) 50%, rgb(255, 255, 255));
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
  align-items: left;
}
.div-row {
  display: flex;
  flex-direction: row;
  align-items: center;
}
.full{
  width: 100%;
  flex-flow: 1;
  font-size: 13px;
   flex-grow: 1;
   align-self:flex-start;
   background-color: rgb(210, 234, 255);
}
.report{
  background-color: antiquewhite;

}.report-item{
  text-align: start
  
}
</style>