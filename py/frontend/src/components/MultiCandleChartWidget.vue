<template>
  <div ref="multi_container" class="grid-stack-item-content border rounded bg-dark text-white shadow-sm">
    <div class="header grid-stack-handle d-flex justify-content-between align-items-center p-2 bg-secondary bg-opacity-25 border-bottom">
      <div class="d-flex align-items-center">
        <span class="me-2">📈</span>
        <strong class="text-uppercase">Chart: {{ currentSymbol }}</strong>

         <select 
          v-model="currentSymbol" 
          @change="handleSymbols"
          class="form-select form-select-sm bg-dark text-white border-secondary timeframe-selector"
        >
          <option
            v-for="s in symbolList"
            :key="s"
            :value="s"
          >
            {{ s }}
          </option>
        </select>
      </div>
       <div class="buttons-right">
        <button @click="selectMode('1m')">1m</button>
        <button @click="selectMode('5m')">5m</button>
        <button @click="selectMode('1h')">5h</button>
        <button @click="selectMode('1d')">1d</button>
        <button @click="selectMode('')">..</button>
      </div>
    </div>

    <div class="position-relative p-0 charts-grid"  style="height: calc(100% - 45px); overflow: hidden;" >
     
        <div v-if="currentMode!=''" style="height:100%" >
          <div class="multi-chart-container">
            <div ref="chartContainer1" class="chart-container cell">
              <CandleChartWidget style="width:100%;height:100%"
                :id="chart_all"
                :ref="el => widgetRefs['chart_all'] = el"
                :symbol="currentSymbol"
                :timeframe=currentMode
                multi_mode=true
                :plot_config="props.plot_config"
              />
            </div>
          </div>
      </div>

      <div v-if="currentMode==''" style="height:100%" >
        
        <div class="multi-chart-container grid-2x2">
            <div ref="chartContainer1" class="chart-container cell">
              <CandleChartWidget style="width:100%;height:100%"
                :id="chart_1"
                :ref="el => widgetRefs['chart_1'] = el"
                :symbol="currentSymbol"
                timeframe="1m"
                multi_mode=true
                :plot_config="props.plot_config"
              />
            </div>

            <div ref="chartContainer2" class="chart-container cell">
              <CandleChartWidget style="width:100%;height:100%"
                :id="chart_2"
                :ref="el => widgetRefs['chart_2'] = el"
                :symbol="currentSymbol"
                timeframe="5m"
                multi_mode=true
                :plot_config="props.plot_config"
              />
            </div>
        
            <div ref="chartContainer3" class="chart-container cell">
              <CandleChartWidget style="width:100%;height:100%"
                :id="chart_3"
                :ref="el => widgetRefs['chart_3'] = el"
                :symbol="currentSymbol"
                timeframe="1h"
                multi_mode=true
                :plot_config="props.plot_config"
              />
            </div>

            <div ref="chartContainer4" class="chart-container cell">
            <CandleChartWidget style="width:100%;height:100%"
                :id="chart_4"
                :ref="el => widgetRefs['chart_4'] = el"
                :symbol="currentSymbol"
                timeframe="1d"
                multi_mode=true
                :plot_config="props.plot_config"
              />
            </div>
        </div>
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import CandleChartWidget from './CandleChartWidget.vue';

const props = defineProps({
  id: { type: String, required: true },
  symbol: { type: String, required: true },
  plot_config: { type: Object, default: () => ({ main_plot: {} }) }
});

const widgetRefs = ref({})

//const emit = defineEmits(['close', 'initialized']);

// Elementi DOM e Variabili reattive

const currentSymbol = ref(props.symbol);
const symbolList = ref([]);
const multi_container = ref(null)

const currentMode = ref("");

// -------------

let timeframes= []

timeframes.push("1m");
timeframes.push("5m");
timeframes.push("1h");
timeframes.push("1d");

const handleSymbols = async () => {
  console.log("handleSymbols",widgetRefs.value["chart_1"])

  widgetRefs.value["chart_1"].setSymbol(currentSymbol.value);
  widgetRefs.value["chart_2"].setSymbol(currentSymbol.value);
  widgetRefs.value["chart_3"].setSymbol(currentSymbol.value);
  widgetRefs.value["chart_4"].setSymbol(currentSymbol.value);

};

function selectMode(mode)
{
  console.log("select ", mode)
  currentMode.value = mode
  resize(0,0);
}

// --- LOGICA REFRESH DATI ---
/*
const handleRefresh = async (index) => {
  try {


    
  } catch (err) {
    console.error("Errore fetch grafico:", err);
  }
};
*/

// --- INIZIALIZZAZIONE ---
onMounted( async() => {
 // console.log("onMounted");

    const responses = await fetch(`http://127.0.0.1:8000/api/symbols`);
    const datas = await responses.json();
    symbolList.value= datas["symbols"];
 
});


const resize =  (w,h) => {
    const rect = multi_container.value.getBoundingClientRect()

    console.log("m resize ",rect,currentMode.value);

    w = Math.max(100,rect.width-40);
    h = Math.max(100,rect.height-40);
    if (currentMode.value?.trim() =="")
    {
      console.log("lll",widgetRefs.value["chart_1"])
      if (widgetRefs.value["chart_1"])   widgetRefs.value["chart_1"].resize(w/2,h/2);
      if (widgetRefs.value["chart_2"])  widgetRefs.value["chart_2"].resize(w/2,h/2);
      if (widgetRefs.value["chart_3"])  widgetRefs.value["chart_3"].resize(w/2,h/2);
      if (widgetRefs.value["chart_4"])  widgetRefs.value["chart_4"].resize(w/2,h/2);
    }
    else
    if (widgetRefs.value["chart_all"])   widgetRefs.value["chart_all"].resize(w-1,h-10);

};


const save = ()=>
{
   //alert("save");
    return {"symbol":currentSymbol.value,"plot_config": props.plot_config}
}


onUnmounted(() => {
 
});

defineExpose({
  resize,
  save
});

</script>

<style scoped>

.charts-grid {
  /*
  display: grid;
  
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  
  flex-wrap: wrap;
  flex-direction: row;

  gap: 4px;
  */
  height: 100%;
}

.grid-2x2 {
  display: grid;
  width: 100%;
  height: 100%;

  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);

  gap: 4px; /* opzionale */
}

.cell {
  padding: 0px;
  margin: 0px;
  box-sizing: border-box;
  min-width: 10;
  min-height: 10;
  height:  100%;
  width: 100%;
  display: flex;
  border: yellow;
  border-width: 0px;
  border-style: dashed;
}

@media (max-width: 768px) {
  .grid-2x2 {
    grid-template-columns: 1fr;
    grid-template-rows: repeat(4, 1fr);
  }
}

.chart-main {
  flex: 1;
}

.chart-volume {
  height: 100px;
  border-top: 1px solid #2b2b43;
}

.chart-legend {
  pointer-events: none;
  background: rgba(19, 23, 34, 0.7);
  border-bottom-right-radius: 4px;
  z-index: 9999 !important;
}
.timeframe-selector {
  width: auto;
  padding: 0 0.5rem;
}
.buttons-right {
  display: flex;
  justify-content: flex-end;
  gap: 8px; /* spazio tra i bottoni */
}
</style>
