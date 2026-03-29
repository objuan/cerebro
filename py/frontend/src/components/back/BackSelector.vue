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

  </div>
</template>

<script setup>
import { ref,watch ,onMounted,computed} from 'vue'
import { staticStore } from '@/components/js/staticStore.js';
import { initProps } from "@/components/js/common";
import {send_get} from  "@/components/js/utils";//send_post
//import SymbolDayMap from '@/components/back/SymbolDayMap.vue'
import {backTest} from "@/components/back/backtest";
//import {BacktestIn}  from '@./back_types.js'

//import { eventBus } from "@/components/js/eventBus";

const emit = defineEmits(['changed']);

//const allSymbolList = ref(null)

//const showPopup = ref(false)
const selectedDate = ref(null)
const dateInput = ref(null)
//const symbolList = ref([])
//const symbolMap = ref(null)
const profile_name = ref(null)


//let profiles = null
//let profile_data = null

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
/*
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
  */

async function fetchHistory(date) {
  console.log("Nuova data:", date)
  let pdata = await send_get("/back/symbols", {date})
  //console.log("symbols:", pdata)
 // allSymbolList.value = pdata
  //symbolMap.value.setup(pdata)
  //backTest.setDate(date)
  backTest.inData.date= selectedDate.value 
  backTest.inData.symbols =  pdata
  await backTest.updateHistoryList()
   
}


// =========================


function saveProfile(){
  staticStore.set("back.history.last",profile_name.value)

  //backTest.inData.date= selectedDate.value 
 // backTest.inData.symbols =  symbolList.value


  backTest.save()
  //send_post("/back/profile/save", {"name": profile_name.value, "data":getData() })
}

onMounted(async  () => {

  await initProps();

  await backTest.load();

   let name = await staticStore.get(
      "back.history.last",""
    )
   profile_name.value=name

   backTest.select(name) 

  if (backTest.inData)
  {
      console.log("data",backTest.inData)

      selectedDate.value = backTest.inData.date
     // symbolList.value = backTest.inData.symbols

      await send_get("/back/enabled",{"enable": true})

      await send_get("/back/profile/select",{"name": name})

      backTest.setHistoryList(await send_get("/back/history/get",{"strategy": backTest.inData.module+"."+backTest.inData.class,"date": backTest.inData.date}))
  }
   emit('changed', { });
 });

 /*
function getSymbolList() {
  return symbolList
}
  */

defineExpose({
 // symbolList,

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
