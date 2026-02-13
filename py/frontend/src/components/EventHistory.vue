<template>
  <div>
    <div class="filter-bar">

      <div class="filter-popup-wrapper">
          <button class="btn btn-sm btn-dark" @click="open = !open">
            Filters ⚙️
          </button>

          <div v-if="open" class="filter-popup">
            <label
              v-for="src in ['order','task-order','error']"
              :key="src"
              class="popup-item"
            >
              <input
                type="checkbox"
                :value="src"
                v-model="allowedSources"
              />
              {{ src }}
            </label>
          </div>
        </div>

      <button  class="btn tiny-btn btn-danger ms-0"  title="Delete Marker Trade"
              @click="clear()">
              x
            </button>
    </div>

    <div class="p-0 items-container">
        <div>

          <MessageWidget
              v-for="ev in sortedEvents"
              :key="ev.name"
              :icon="ev.icon"
              :symbol = ev.symbol
              :timestamp = ev.ts
              :title = ev.subtype
              :text="ev.summary"
              :detail="ev.message"
              :color="ev.color"
            >
          </MessageWidget>


        </div>
    </div>
</div>
</template>

<script setup>
import {  ref,onMounted,onBeforeUnmount,watch,computed } from 'vue'
import { eventStore as store } from "@/components/js/eventStore";
import MessageWidget from "@/components/MessageWidget.vue";
import { send_get } from '@/components/js/utils';
import { staticStore } from '@/components/js/staticStore.js';
import { eventBus } from "@/components/js/eventBus";

const open = ref(false)
const allowedSources = ref(['order','task-order','error']);

const sortedEvents = computed(() =>
{

 return [...store.items]
    .filter(e => allowedSources.value.includes(e.source))
    .sort((a, b) => b.timestamp - a.timestamp)
    
}
);


function clear() {
  store.clear();
}

async function onStart(){
     let filter = staticStore.get('event.filter_events');
    //console.log("allowedSources filter:", filter)
      
    if (filter){
    
      allowedSources.value = JSON.parse(filter)
    }

    await send_get("/api/event/get",{"limit":50, "types":  ['order','task-order','error']})
    //console.log("event ",pdata )
    /*
    store.clear()
    pdata.forEach(  (val) =>{
      val.data = JSON.parse(val.data)
      store.push(val)    
    });
*/

}
onMounted( async () => {
    eventBus.on("on-start", onStart)
});

onBeforeUnmount(() => {
  eventBus.off("on-start", onStart)
});

watch(allowedSources, (newVal, ) => {
  
  let v = JSON.stringify(newVal)
 // console.log("allowedSources cambiato:", newVal,v)

  staticStore.set('event.filter_events',v)
  //saveProp("event.filter",v)
}, { deep: true })

</script>

<style scoped>
.popup-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  color: white;
  cursor: pointer;
}

.tiny-btn {
  padding: 0 1px;
  font-size: 10px;
  line-height: 1;
  min-width: 20px;
  height: 20px;
}


.filter-bar{
  display:flex;
  gap:12px;
  padding:1px;
  background:#111;
  color:white;
  font-size:13px;
  border-bottom:2px solid #333;
}

.filter-item{
  display:flex;
  align-items:center;
  gap:6px;
  cursor:pointer;
}
.filter-popup-wrapper {
  position: relative;
  display: inline-block;
}

.filter-popup {
  position: absolute;
  top: 110%;
  right: 100;
  background: #1b1b1b;
  border: 1px solid #444;
  padding: 8px 10px;
  border-radius: 6px;
  z-index: 1000;
  min-width: 140px;

  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}


.items-container {
   height: calc(100vh - 130px); 
  overflow-y: auto;
  overflow-x: hidden;   /* ❌ niente scroll orizzontale */
  width: 100%;
  margin-right: 2px;
}
.items-container::-webkit-scrollbar {
  width: 6px;              /* sottile */
}

.items-container::-webkit-scrollbar-track {
  background: #111;
}

.items-container::-webkit-scrollbar-thumb {
  background: #555;
  border-radius: 4px;
}

.items-container::-webkit-scrollbar-thumb:hover {
  background: #888;
}
.items-container {
  scrollbar-width: thin;
  scrollbar-color: #555 #111;
}


/*
.body {
  overflow-y: auto;
  max-height: 60vh;
}

.row {
  padding: 8px 10px;
  border-bottom: 1px solid #1e293b;
  font-size: 13px;
}

.row.error { border-left: 4px solid #ef4444; }
.row.warning { border-left: 4px solid #f59e0b; }
.row.info { border-left: 4px solid #3b82f6; }

.time {
  font-size: 16px;
  opacity: 1.6;
  margin-bottom: 4px;
}

.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none;
}

.toast {
   display: block;
  pointer-events: auto;
  min-width: 300px;
  max-width: 420px;
  padding: 14px 16px;
  border-radius: 10px;
  color: #fff;
  box-shadow: 0 10px 30px rgba(0,0,0,0.35);
  font-family: system-ui;
  animation: fadein 0.2s ease;
  cursor: pointer;
  border-left: 6px solid transparent;
}

.toast .header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 6px;
}

.toast .msg {
  font-size: 0.9rem;
  opacity: 0.95;
}

// TIPI 

.toast.error {
  background: #1f2937;
  border-left-color: #ef4444;
}

.toast.warning {
  background: #1f2937;
  border-left-color: #f59e0b;
}

.toast.info {
  background: #1f2937;
  border-left-color: #3b82f6;
}

// Animazioni 

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(60px);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}

.order {
  background: #307927;
  border-left-color: #3b82f6;
}

.task {
  background: #3a2a68;
  border-left-color: #3b82f6;
}
.general {
  background: #6d2026;
  border-left-color: #3b82f6;
}

*/
</style>