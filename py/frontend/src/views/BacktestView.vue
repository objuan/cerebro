<template>
  <div class="home">

    <PageHeader title="Cerebro V0.1" style="margin-left: 30px;margin-right: 30px;"/>
 
   
    <HistoryBrowser ref="history" @changed="onHistoryChanged"></HistoryBrowser>
    
    <main class="main-columns">

      <div class="items-container">
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
        </div>

        <div>
          <MultiBackChartWidget class="back-chart"
            ref ="multiBackChartWidget"
            id="back"
            :number="1"
            :symbol="selectedSymbol"
            :timeframe ="currentTimeframe"
          />
        </div>
        <div>2</div>
   
      </main>
  </div>


</template>

<script setup>
import { onMounted,ref} from 'vue';
import PageHeader from '@/components/PageHeader.vue'
import HistoryBrowser from '@/components/back/HistoryBrowser.vue'
//import { tickerStore as tickerList } from "@/components/js/tickerStore";
import { initProps } from "@/components/js/common";
import MultiBackChartWidget from '@/components/back/MultiBackChartWidget.vue'

const history = ref(null)
const symbolList = ref(null)
const currentTimeframe = ref(null)
const selectedSymbol = ref("")
const multiBackChartWidget = ref(null)

//const symbolList = ref(null)
/*
const symbolList = computed( ()=>
{
  console.log("history",history)
  //return history.value?.symbolList ?? []
}
);
*/
  //)

function onSymbolClick(symbol){
  selectedSymbol.value = symbol
}

function onHistoryChanged(){
     console.log("onHistoryChanged")

     symbolList.value = history.value.symbolList

     selectedSymbol.value = symbolList.value [0].symbol
     currentTimeframe.value =history.value.currentTimeframe

}


onMounted( async () => {
  
  await initProps();
});


/*
watch(history.value.symbolList, async (newValue, oldValue)  => {
  if (newValue == null) return;
  if (oldValue && oldValue!= newValue)
  {
    console.log("symbolList",history.value.symbolList)
  }
});
*/

</script>

<style scoped>

.back-chart{
  height: 100%;
}
.main-columns {
  display: grid;
   grid-template-columns: 160px 1fr 180px ;
  gap: 1px;
  flex: 1;
  
  margin-left: 2px;
  
  overflow: hidden;
}

.items-container {
   height: calc(100vh - 140px); 
  overflow-y: auto;
  overflow-x: hidden;   /* ❌ niente scroll orizzontale */
  width: 100%;
  margin-right: 2px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;  /* 🔥 allinea in alto */
  align-items: stretch;         /* opzionale */
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