<template>
  <div ref="multi_container" @mousedown="handleSelect" class="grid-stack-item-content border rounded bg-dark text-white shadow-sm">
    <div class="header grid-stack-handle d-flex justify-content-between align-items-center p-2 bg-secondary bg-opacity-25 border-bottom">
      <div class="d-flex align-items-center">
         <span class="me-2" >📈</span>
         <strong class="text-uppercase">{{number}} 
          Chart: <span style="color:yellow">{{ currentSymbol }}</span>
        </strong>
          
         <select 
          v-model="currentSymbol" 
          @change="onChangeSymbols"
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
        <div style="margin-left:20px; display:flex; flex-direction:column; align-items:flex-end; justify-content:center; ">
             <span v-html="fundamentals"></span>
            <span class="ticker" v-html="ticker"></span>
        </div>
      </div>
       <div class="buttons-right">

          <select 
            v-model="currentLayout" 
            @change="onChangeLayouts"
            class="form-select form-select-sm bg-dark text-white border-secondary timeframe-selector"
          >
            <option value="1,1">1x1</option>
            <option value="1,2">1x2</option>
            <option value="2,1">2x1</option>
            <option value="2,2">2x2</option>
          </select>

           <button
            v-for="tf in timeframes"
            :key="tf"
            @click="selectMode(tf)"
          >
            {{ tf }}
          </button>
        <button @click="selectMode('')">..</button>
      </div>
    </div>

    <div class="trade_console p-0">
        <TradeConsole :symbol=symbol  ></TradeConsole> 
    </div>

    <div class="position-relative p-0 charts-grid"  style="height: calc(100% - 120px); overflow: hidden;" >
     
        <div v-if="currentMode!=''" style="height:100%" >
          <div class="multi-chart-container"  style="height:100%" >
            <div ref="chartContainer1" class="chart-container cell">
              <CandleChartWidget style="width:100%;height:100%"
                id="_chart_all"
                :ref="el => widgetRefs['_chart_all'] = el"
                :symbol="currentSymbol"
                :timeframe=currentMode
                :multi_mode=false
                :plot_config="props.plot_config"
              />
            </div>
          </div>
      </div>

      <div v-if="currentMode==''" style="height:100%" >
        
        <div class="multi-chart-container grid-2x2">
            <div ref="chartContainer1" class="chart-container cell">
              <CandleChartWidget style="width:100%;height:100%"
                id="_chart_1"
                :ref="el => widgetRefs['_chart_1'] = el"
                :symbol="currentSymbol"
                timeframe="5m"
                :multi_mode=true
                :plot_config="props.plot_config"
              />
            </div>

            <div ref="chartContainer2" class="chart-container cell">
              <CandleChartWidget style="width:100%;height:100%"
                id="_chart_2"
                :ref="el => widgetRefs['_chart_2'] = el"
                :symbol="currentSymbol"
                timeframe="1m"
                :multi_mode=true
                :plot_config="props.plot_config"
              />
            </div>
        
            <div ref="chartContainer3" class="chart-container cell">
              <CandleChartWidget style="width:100%;height:100%"
                id="_chart_3"
                :ref="el => widgetRefs['_chart_3'] = el"
                :symbol="currentSymbol"
                timeframe="1d"
                :multi_mode=true
                :plot_config="props.plot_config"
              />
            </div>

            <div ref="chartContainer4" class="chart-container cell">
            <CandleChartWidget style="width:100%;height:100%"
                id="_chart_4"
                :ref="el => widgetRefs['_chart_4'] = el"
                :symbol="currentSymbol"
                timeframe="10s"
                :multi_mode=true
                :plot_config="props.plot_config"
              />
            </div>
        </div>
      </div>
    </div>
   
  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted,onBeforeUnmount } from 'vue';
import CandleChartWidget from './CandleChartWidget.vue';
import { computed } from 'vue';
import  TradeConsole  from './TradeConsole.vue'
import { eventBus } from "@/components/js/eventBus";
import {send_post} from '@/components/js/utils.js'

const props = defineProps({
  id: { type: String, required: true },
  number: { type: Number, required: true },
  symbol: { type: String, required: true },
  timeframe_multi: { type: String, required: false,default:"10s,1m,5m,1d" },
  timeframe: { type: String, required: false ,default:"10s"},
  plot_config: { type: Object, default: () => ({ main_plot: {} }) }
});

const widgetRefs = ref({})

// Elementi DOM e Variabili reattive

const currentSymbol = ref(props.symbol);
const fundamentals = ref("")  
const ticker = ref("")  
const symbolList = ref([]);
const multi_container = ref(null)
const currentLayout= ref("")  

const currentMode = ref(props.timeframe );

const emit = defineEmits(['select'])
function handleSelect() {
  emit('select', props.id)
}

// -------------

const timeframes = computed(() =>
  props.timeframe_multi
    .split(',')
    .map(tf => tf.trim())
    .filter(Boolean)
);

const onChangeLayouts = async () => {
};

const onChangeSymbols = async () => {
  console.log("onChangeSymbols",widgetRefs.value["_chart_1"])
  if (currentMode.value?.trim() =="")
  {
    widgetRefs.value["_chart_1"].setSymbol(currentSymbol.value);
    widgetRefs.value["_chart_2"].setSymbol(currentSymbol.value);
    widgetRefs.value["_chart_3"].setSymbol(currentSymbol.value);
    widgetRefs.value["_chart_4"].setSymbol(currentSymbol.value);
  }
  else
    widgetRefs.value["_chart_all"].setSymbol(currentSymbol.value);

    send_post('/api/props/save', { path: 'chart.'+props.number, value: currentSymbol.value });
};


function selectMode(mode)
{
  //console.log("select ", mode)
  currentMode.value = mode
  resize();
}

// --- INIZIALIZZAZIONE ---
onMounted( async() => {
 // console.log("onMounted");
    eventBus.on("ticker-received", onTickerReceived);

    let responses = await fetch(`http://127.0.0.1:8000/api/symbols`);
    let datas = await responses.json();
    symbolList.value= datas["symbols"];

    await updateAll();

});

onBeforeUnmount(() => {
  eventBus.off("ticker-received", onTickerReceived);
});

const updateAll = async ()=>
{
    let responses = await fetch(`http://localhost:8000/api/fundamentals?symbol=${currentSymbol.value} `);
    let datas = await responses.json();
    //console.log("fundamentals ",datas); 

    //fundamentals.value= datas["exchange"] + " " + datas["sector"] + " MktCap: " + (datas["market_cap"]/1e9).toFixed(2) + "B" ;
    fundamentals.value= " MktCap: " + window.formatValue(datas["market_cap"])  ;
    fundamentals.value+= "  FLOAT: <span style='color:yellow'><b>" + window.formatValue(datas["float"]) + "</b></span> / "+ window.formatValue(datas["shares_outstanding"])   ;
}

const setSymbol = async (symbol) => {
  currentSymbol.value = symbol
  await updateAll();
  onChangeSymbols()
//  handleRefresh();
};


const resize =  () => {
   
    //console.log("m resize ",w,h);

    if (currentMode.value?.trim() =="")
    {
      //console.log("lll",widgetRefs.value["chart_1"])
      if (widgetRefs.value["_chart_1"])   widgetRefs.value["_chart_1"].resize();
      if (widgetRefs.value["_chart_2"])  widgetRefs.value["_chart_2"].resize();
      if (widgetRefs.value["_chart_3"])  widgetRefs.value["_chart_3"].resize();
      if (widgetRefs.value["_chart_4"])  widgetRefs.value["_chart_4"].resize();
    }
    else
        if (widgetRefs.value["_chart_all"])   widgetRefs.value["_chart_all"].resize();

};


const save = ()=>
{
   //alert("save");
    return {"symbol":currentSymbol.value,"plot_config": props.plot_config}
}

function on_candle(msg)
{
  if (currentMode.value  != "" && currentMode.value  == msg ["tf"])
  {
        //console.log("MultiCandleChartWidget on_candle",msg) 
        widgetRefs.value['_chart_all']?.on_candle(msg);  
  }
  else{
      widgetRefs.value['_chart_1']?.on_candle(msg);  
      widgetRefs.value['_chart_2']?.on_candle(msg);  
      widgetRefs.value['_chart_3']?.on_candle(msg);  
      widgetRefs.value['_chart_4']?.on_candle(msg);  
  }
}
function onTickerReceived(msg)
{
  if (msg["symbol"] == currentSymbol.value)
  {
      let color = msg["gain"]>=0 ? '#4bffb5' : '#ff4976';  
      //console.log("MultiCandleChartWidget on_ticker",msg) 
      ticker.value= ` Last: <span style='color:yellow'><b> ${msg["last"]} </b></span>  Gain: <span style='color:${color}'><b>${msg["gain"].toFixed(2)} %</b></span>  Vol: ${window.formatValue(msg["volume"])}`  ;
  }
}

onUnmounted(() => {
 
});

defineExpose({
  resize,
  save,
  on_candle,
  setSymbol
});

</script>

<style scoped>


.charts-grid {
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
  overflow: hidden;
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
.ticker{
  display: block;      /* necessario per text-align */
  text-align: right ;
  margin-left: auto;
  align-self: flex-end;
}
.trade_console{
  height: 80px;
  border: #0077ff solid    ;
  border-width: 1;
}
</style>
