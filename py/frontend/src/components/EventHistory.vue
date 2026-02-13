<template>
  <div>
    <div class="filter-bar">

      <div class="filter-popup-wrapper">
          <button class="btn btn-sm btn-dark" @click="open = !open">
            Filters ⚙️
          </button>

          <div v-if="open" class="filter-popup">
            <label
              v-for="src in ['order','task-order','error','message']"
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
import { staticStore } from '@/components/js/staticStore.js';
import { eventBus } from "@/components/js/eventBus";

const open = ref(false)
const allowedSources = ref(['order','task-order','error']);

const sortedEvents = computed(() =>
{

 return [...store.items]
    .filter(e => allowedSources.value.includes(e.source))
    .sort((a, b) => b.ts - a.ts)
    
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

    //await send_get("/api/event/get",{"limit":50, "types":  ['order','task-order','error']})
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
   height: calc(100vh - 90px); 
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

</style>