<template>
  <div  class="event"
    :style="{ '--event-bg': props.color || '#ccc' }">
  
    <!-- HEADER -->
  
    <div class="event-header">
              <div style="max-width: 18px;"> {{ props.icon }}</div>
              <div :class="['time', { 'new-bar': isNew }]">
                {{ getDate() }}
              </div>
              <div class="title">{{ props.title }}</div>
            
    </div>

    <!-- BODY -->
    <div class="div-col body">

        <div class ="div-row" >
              <div class="symbol fw-bold">
                      <a
                        href="#"
                        class="text-blue-600 hover:underline"
                        @click.prevent="onSymbolClick(props.symbol)"
                      >
                        {{ props.symbol }}
                      </a>
              </div>

              <div class="msg" 
                :style="process_text(props.text).style" 
                v-html="process_text(props.text).text">
             </div>

              <button class="toggle-btn" @click="toggle">
                <svg v-if="!open" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                  <!-- chevron down = open -->
                  <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2"/>
                </svg>

                <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                  <!-- chevron up = close -->
                  <path d="M6 15l6-6 6 6" fill="none" stroke="currentColor" stroke-width="2"/>
                </svg>
            </button>

          </div>
           
         <!-- detail -->
          <div  v-if="open" class="full" >

                 
                      <div class="div-col">
                        <div v-if="props.detail">

                          <div class="msg" v-html="props.detail"></div>
                        </div>
                        <div v-if="reportDetails && reportDetails.summary" class="report">
                          <div class="report-item" >Rank:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; &nbsp;&nbsp;{{ reportDetails.rank }}</div>
                          <div class="report-item"  :style="{ color: priceColor(reportDetails.summary.gain) }">
                            From Close: {{ formatValue(reportDetails.gain) }}%
                          </div>
                          <div class="report-item"  :style="{ color: priceColor(reportDetails.summary.gap) }">
                              Gap: &nbsp;{{ formatValue(reportDetails.gap) }}%</div>
                          <div class="report-item">Volume: {{ formatValue(reportDetails.day_volume) }}</div>

                          <div class="report-item">Float:&nbsp;&nbsp;&nbsp; {{ formatValue(reportDetails.float) }}</div>
                          <div class="report-item" :style="{ color: volumeRelColor(reportDetails.summary.rel_vol_5m) }">
                                Rel 5: &nbsp;&nbsp;&nbsp;{{ formatValue(reportDetails.rel_vol_5m) }}</div>
                          <div class="report-item" :style="{ color: volumeRelColor(reportDetails.summary.rel_vol_24) }">
                                Rel 24:&nbsp; {{ formatValue(reportDetails.rel_vol_24) }}</div>
                          
                          <div class="report-item" :style="{color:newsColor(reportDetails.summary.news-1)}">News:&nbsp; {{ reportDetails.news }}</div>
                          
                          
                        </div>
                      </div>
          </div>
    </div>
  </div>
</template>

<script setup>

import { ref,onMounted, onUnmounted ,onBeforeUnmount,watch } from 'vue';

//import { send_get } from '@/components/js/utils';
import { reportStore as report } from "@/components/js/reportStore";
import { formatValue,priceColor,newsColor,volumeRelColor,color_ramp} from "@/components/js/utils";// scaleColor
import { eventBus } from "@/components/js/eventBus";

const props = defineProps({
  icon: { type: String, required: false, default:"" },
  symbol: { type: String, required: false ,default:""},
  title: { type: String, required: true },
  timestamp: { required: true },
  color: { type: String, required: false,default:"" },

  text: { type: String, required: false },
  detail: { type: String, required: false },
});


let reportDetails = null // key -> result
const isNew = ref(true)
const open = ref(false)

function my_ramp_perc(v, color){
  const f =  Math.min(10,v) / 10
  return `background-color:${color_ramp(f,color,props.color)};`
}

function process_text(text){
   if (!text.trim().startsWith("<span"))
     return {"text":  text, "style":null}

  const scope = { my_ramp_perc }

  //console.log(text)
  let style =  {color: 'black'}
   const m = text.match(/:style\s*=\s*(['"])(.*?)\1/)
   if (m) 
   {
    // console.log("CALL",m)

     const expr = m[2]
     const fnMatch = expr.match(/^\s*(\w+)\s*\((.*)\)\s*$/)
      if (fnMatch) 
      {
      //  console.log("fnMatch",fnMatch)
        const fnName = fnMatch[1]
        const argsRaw = fnMatch[2]

         
      // split argomenti gestendo stringhe
        const args = Function(`return [${argsRaw}]`)()

        if (typeof scope[fnName] === "function")
      {
        
       // console.log("CALL",fnName,args)
        try{
          style =  scope[fnName](...args)

           // style console.log("RET",ret)
        }
        catch(e){
          console.error(e)
        }
      }

      }
    //let ret =  scope[fnName](...args)
    //console.log("ret",ret)
   }
 
  return {"text":  text, "style":style}
}


function getDate(){
  try{
  return new Date(props.timestamp).toLocaleTimeString()
  }catch{
    return props.timestamp;
  }
  
}
function toggle() {

  open.value = !open.value
  if (open.value  && reportDetails==null)
  {
   //  console.log("fullDetails")

    reportDetails = report.get_report(props.symbol)
    if (reportDetails)
        reportDetails.summary =  report.get_sum_rank(props.symbol)

     //console.log("reportDetails",reportDetails)
  }

 // console.log("fullDetails",fullDetails)
}

function ramp_perc(value,color){
 console.log(value,color)
}

console.debug(ramp_perc)
// Esponiamo i dati dello store al template

function onSymbolClick(symbol) {
  console.log('Symbol clicked:', symbol)
  eventBus.emit("chart-select",{"symbol" : symbol , "id": "chart_1"});
}


const checkNew = () => {
  const dt = new Date(props.timestamp)
  const diffSeconds = (Date.now() - dt.getTime()) / 1000

  //console.log("diffSeconds", dt, diffSeconds, props.title)

  if (diffSeconds < 10) {
    isNew.value = true
    setTimeout(() => {
      isNew.value = false
    }, 60_000)
  } else {
    isNew.value = false
  }
}

onMounted( async () => {
   checkNew();
});

onBeforeUnmount(() => {
});

onUnmounted(() => {
});

watch(() => props.timestamp, () => {
  checkNew()
})

</script>

<style scoped>

/* Barra superiore lampeggiante */
.new-bar {
  
  background: linear-gradient(90deg, transparent, #00ffea, transparent);
  animation: alert-blink 2.0s ease-in-out infinite alternate;
}

@keyframes alert-blink {
   from {
    opacity: 0.9;
    transform: translateX(0%);
  }
  to {
    opacity: 1;
    transform: translateX(30%);  /* (100 / 30) - 1 ≈ quanto serve per arrivare a destra */
  }
}

.event {
  width: 100%;
  min-height: 60px;
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
 margin-right: auto
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
  background-color: rgb(77, 77, 77);
  color:white;

}.report-item{
  text-align: start
  
}

.toggle-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.toggle-btn svg {
  width: 18px;
  height: 18px;
  transition: transform 0.2s ease;
}

.toggle-btn:hover svg {
  transform: scale(1.2);
}
</style>