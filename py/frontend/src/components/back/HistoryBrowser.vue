<template>
  <div class="history-browser">

    <div class="history-header">

      <h3>HistoryBrowser</h3>

      <span>Profile</span>
      <input type="string"  v-model="profile_name"/>
    
      <button @click="saveProfile" class="btn btn-success">
          Save
      </button> 

      <input
        ref="dateInput"
        type="date"
        v-model="selectedDate"
        class="hidden-date"
      />
     <div class="local-date">
        {{ formattedDate }}
      </div>
      <button @click="openPicker" class="btn btn-success">
        📅 
      </button> 

      <button @click="openPopup" class="btn btn-success">
          Symbol Map
      </button>

      <select 
          v-model="currentTimeframe" 
          @change="onTimeFrameChange" 
          class="form-select form-select-sm bg-dark text-white border-secondary timeframe-selector"
        >
          <option value="10s">10s</option>
          <option value="30s">30s</option>
          <option value="1m">1m</option>
          <option value="5m">5m</option>
          <option value="1h">1h</option>
          <option value="1d">1d</option>
        </select>

    </div>
  <!--    -->

  <div>
    <!--
      <div
        v-for="item in symbolList"
        :key="item.symbol"
        class="card ticket-card"
      >
        <div class="card-body p-2 d-flex justify-content-between align-items-center">

            <div class="fw-bold">
                <a href="#" class="text-blue-600 hover:underline" @click.prevent="onSymbolClick(item.symbol)">
                      {{ item.symbol }}
                    </a>

            </div>
          </div>
      </div>
      -->
  </div>

  <!-- -->

      <div>
         <!-- POPUP -->
        <div v-if="showPopup" class="overlay" @click.self="closePopup">
          <div class="modal">
            <button class="close" @click="closePopup">✕</button>

            <SymbolDayMap ref="symbolMap" />
          </div>
        </div>

    </div>

  </div>
</template>

<script setup>
import { ref,watch ,onMounted,computed,nextTick} from 'vue'
import { staticStore } from '@/components/js/staticStore.js';
import { initProps } from "@/components/js/common";
import {send_get,send_post} from  "@/components/js/utils";
import SymbolDayMap from '@/components/back/SymbolDayMap.vue'

//import { eventBus } from "@/components/js/eventBus";

const emit = defineEmits(['changed']);

const allSymbolList = ref(null)

const showPopup = ref(false)
const selectedDate = ref(null)
const dateInput = ref(null)
const symbolList = ref([])
const symbolMap = ref(null)
const profile_name = ref(null)
const currentTimeframe = ref("1m")

let profiles = null
let profile_data = null

// =========================

const formattedDate = computed(() => {
  if (!selectedDate.value) return ""
  const date = new Date(selectedDate.value)
  return date.toLocaleDateString()
})

function openPicker() {
  dateInput.value.showPicker() // 🔥 apre il date picker
}

watch(selectedDate, (newDate) => {
  //staticStore.set("back.history.date", newDate)
  fetchHistory(newDate)
})

// =========================

async  function openPopup() {
  showPopup.value = true
  await nextTick()
  symbolMap.value.setup(allSymbolList.value)
}

function closePopup() {
  showPopup.value = false
  symbolList.value = symbolMap.value.selectedSymbols.map(s => ({
    symbol: s
  }))

  emit('changed', { });
}

async function fetchHistory(date) {
  console.log("Nuova data:", date)
  let pdata = await send_get("/back/symbols", {date})
  console.log("symbols:", pdata)
  allSymbolList.value = pdata
  //symbolMap.value.setup(pdata)
}

// =========================
function onTimeFrameChange(){
  emit('changed', { });
}

function getData(){
  staticStore.set("back.history.last",profile_name.value)
  return {
    "symbols" : symbolList.value,
    "date" : selectedDate.value,
    "tf" : currentTimeframe.value

  }
}
function saveProfile(){
  send_post("/back/profile/save", {"name": profile_name.value, "data":getData() })
}

onMounted(async  () => {

  await initProps();

  profiles = await send_get("/back/profiles")
  let name = await staticStore.get(
      "back.history.last",""
    )
  profile_name.value=name
   const profile = profiles.find(
      p => p.name === name
    )
  profile_data = profile ? profile.data : null
  if (profile_data!=null)
  {
      let data = JSON.parse(profile_data)
      console.log("data",data)

      selectedDate.value = data.date
      symbolList.value = data.symbols
      currentTimeframe.value = data.tf


      send_get("/back/profile/select",{"name": name})
  }
   emit('changed', { });
 });

 /*
function getSymbolList() {
  return symbolList
}
  */

defineExpose({
  getData,
  symbolList,
  currentTimeframe
});


</script>


<style scoped>

/* overlay scuro */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

/* finestra */
.modal {
  background: white;
  width: 90%;
  display: block;
  max-width: 1200px;
  max-height: 90vh;
  overflow: auto;
  border-radius: 8px;
  padding: 20px;
  position: relative;
}

/* bottone chiusura */
.close {
  position: absolute;
  top: 10px;
  right: 10px;
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
}

.history-header{
  display: flex;
  flex-direction: row;
  gap: 10px;
}
.history-browser {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.local-date {
  font-weight: 500;
}
/* nasconde input ma lo mantiene funzionale */
.hidden-date {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
</style>
