<template>
  <div>
    <div class="filter-bar">
      <label v-for="src in ['mule','strategy']" :key="src" class="filter-item">
        <input
          type="checkbox"
          :value="src"
          v-model="allowedSources"
        />
        {{ src }}
      </label>
    </div>

     <div class=" d-flex flex-wrap gap-0 justify-content-end align-content-start events-container">

       <MessageWidget
          v-for="event in sortedEvents"
          :key="event.timestamp + event.symbol + event.name"
          :symbol = event.symbol
          :timestamp = event.timestamp
          :title = event.name
          :text="event.data.small_desc"
          :detail="event.data.full_desc"
          :color="event.data.color"
        >
      </MessageWidget>
    </div>
  </div>
</template>

<script setup>

import { ref,computed,onMounted, onUnmounted ,onBeforeUnmount,watch } from 'vue';

import { eventBus } from "@/components/js/eventBus";
import { strategyStore as store } from "@/components/js/strategyStore";
import { send_get } from '@/components/js/utils';
//import { formatValue} from "@/components/js/utils";// scaleColor
import { staticStore } from '@/components/js/staticStore.js';
//import {saveProp} from '@/components/js/utils.js'
import MessageWidget from "@/components/MessageWidget.vue";

const allowedSources = ref(['mule', 'strategy']);

const sortedEvents = computed(() =>
{
 return [...store.items]
    .filter(e => allowedSources.value.includes(e.source))
    .sort((a, b) => b.timestamp - a.timestamp)
}
);


defineProps({
})

async function onStart(){
    let pdata = await send_get("/api/event/get")
    //console.log("event ",pdata )
    store.clear()
    pdata.forEach(  (val) =>{
      val.data = JSON.parse(val.data)
      store.push(val)    
    });

   let filter = staticStore.get('event.filter');
    //console.log("allowedSources filter:", filter)
      
    if (filter){
    
      allowedSources.value = JSON.parse(filter)
    }
}
onMounted( async () => {
    eventBus.on("on-start", onStart)
});

onBeforeUnmount(() => {
});

onUnmounted(() => {
});

/*
watch(
  () => liveStore.get('event.filter'),
  v => {
      console.log("allowedSources",v)
    if (v != null) allowedSources.value = v;
  },
  { immediate: true }
);
*/
watch(allowedSources, (newVal, ) => {
  
  let v = JSON.stringify(newVal)
 // console.log("allowedSources cambiato:", newVal,v)

  staticStore.set('event.filter',v)
  //saveProp("event.filter",v)
}, { deep: true })


</script>

<style scoped>
.filter-bar{
  display:flex;
  gap:12px;
  padding:6px;
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

.events-container {
  height: 90vh;
  overflow-y: auto;
  width: 100%;
  margin-right: 2px;
}


</style>