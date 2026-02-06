<template>
  <div ref="multi_container" @mousedown="handleSelect" class="border rounded bg-dark text-white shadow-sm">
    <div class="chart-header">
      <div class="top-row">
         <strong class="text-uppercas symbol">({{number}} )
          <span class="symbol">{{ currentSymbol }} </span>
          <span class="positon">#{{ position }}</span>
        </strong>
          
        <select 
          v-model="currentSymbol" 
          @change="onChangeSymbols"
          class=" form-select-sm bg-dark text-white border-secondary "
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

        <div  class="middle-row" style="margin-left:20px; display:flex; flex-direction:column;justify-content:center; ">
             <span v-html="fundamentals"></span>
            <span class="ticker" v-html="ticker"></span>
        </div>
       
        <div class="bottom-row">
     
          <select 
            v-model="currentLayout" 
            @change="onChangeLayouts"
            class="form-select-sm bg-dark text-white border-secondary "
          >
            <option value="1_1">1x1</option>
            <option value="1_2">1x2</option>
            <option value="2_1">2x1</option>
            <option value="2_2">2x2</option>
          </select>
      </div>
    </div>

    <div class="trade_console p-0">
        <TradeConsole :symbol=currentSymbol  ></TradeConsole> 
    </div>

  
         <div class="in-charts-grid" :style="gridStyle">
          <CandleChartWidget
              v-for="cell in cells"
              :key="cell.id"
              :ref="el => widgetRefs[cell.id] = el"
              :id="cell.id"
              :symbol="currentSymbol"
              :timeframe="cell.timeframe"
              :plot_config="cell.plot_config"
              
              :number="number"
              :sub_number ="cell.number"
              :grid ="grid"
          >
          </CandleChartWidget>
        </div>

              
    

  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted,onBeforeUnmount,nextTick,watch } from 'vue';
import CandleChartWidget from './CandleChartWidget.vue';
import { computed } from 'vue';
import  TradeConsole  from './TradeConsole.vue'
import { eventBus } from "@/components/js/eventBus";
import {saveProp,send_get} from '@/components/js/utils.js'
//import { liveStore } from '@/components/js/liveStore.js';
import { staticStore } from '@/components/js/staticStore.js';

const props = defineProps({
  id: { type: String, required: true },
  number: { type: Number, required: true },
  symbol: { type: String, required: true },
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
const rows = ref(1)
const cols = ref(1)
const cells = ref([])  // contiene i widget attivi
const position = ref(null);

const emit = defineEmits(['select'])
function handleSelect() {
  emit('select', props.id)
}

const get_layout_key = (subkey)=> { return `chart.${props.number}.${subkey}`}

// -------------

const grid = computed( ()=>{
  return `${rows.value}_${cols.value}`
})

const gridStyle = computed(() => ({
  display: 'grid',
  width: '100%',
  //height: '100%',
  height: 'calc(100% - 140px)',
  gridTemplateColumns: `repeat(${cols.value}, 1fr)`,
  gridTemplateRows: `repeat(${rows.value}, 1fr)`,
  gap: '6px',
}))

const onChangeLayouts = async () => {
    const [r, c] = currentLayout.value.split("_").map(Number);
    rows.value = r
    cols.value = c
    widgetRefs.value={}
    const total = r * c
    const newCells = []

    for (let i = 0; i < total; i++) {
       //let tf =  staticStore.get( get_layout_key("layout."+(i+1)+".timeframe"),"1m")
    //   let key = get_layout_key(`${grid.value}.${(i+1)}.timeframe`)
      // console.log(key)
       let tf =  staticStore.get( get_layout_key(`${grid.value}.${(i+1)}.timeframe`),"1m")
        
       newCells.push({
        id: crypto.randomUUID(),
        number: i+1,          // posizione nella griglia (0 → n-1)
        plot_config: {},
        timeframe:tf
       });
      }
    
  cells.value = newCells
  
  saveProp(get_layout_key("grid"),grid.value );

  nextTick(resize)
};



const onChangeSymbols = async () => {

   currentLayout.value = staticStore.get( get_layout_key("grid"),"1_1")
  
   //console.log("onChangeSymbols", currentLayout.value);

   for (const id in widgetRefs.value) {
        const comp = widgetRefs.value[id]
        const el = comp?.$el
        if (!el) continue
 
        comp.setSymbol(currentSymbol.value);
        
   }

    saveProp( get_layout_key("symbol"), currentSymbol.value );
};

// --- INIZIALIZZAZIONE ---
onMounted( async() => {
 // console.log("onMounted");
    eventBus.on("ticker-received", onTickerReceived);
    eventBus.on("update-portfolio", onPositionUpdated);
    eventBus.on("update-position", onPositionUpdated);

    let responses = await fetch(`http://127.0.0.1:8000/api/symbols`);
    let datas = await responses.json();
    symbolList.value= datas["symbols"];

    await updateAll();

    // --------------
    currentLayout.value = staticStore.get(get_layout_key("grid"),"1_1")
    
    let pos_list = await send_get('/account/positions')
    pos_list.forEach(  (val) =>{
          val["type"] = "POSITION"
          onPositionUpdated(val);
    });
    
    onChangeLayouts()
});

onBeforeUnmount(() => {
  eventBus.off("ticker-received", onTickerReceived);
   eventBus.off("update-portfolio", onPositionUpdated);
  eventBus.off("update-position", onPositionUpdated);
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

    for (const id in widgetRefs.value) {
        const comp = widgetRefs.value[id]
        const el = comp?.$el
        if (!el) continue
        const rect = el.getBoundingClientRect()
        comp.resize(rect.width, rect.height)
   }

};


const save = ()=>
{
   //alert("save");
    return {"symbol":currentSymbol.value,"plot_config": props.plot_config}
}

function on_candle(msg)
{
  if (msg.s == currentSymbol.value)
  {
      //console.log("FIND ", currentSymbol.value,widgetRefs)
      for (const id in widgetRefs.value) {
        const comp = widgetRefs.value[id]
        if (comp)
          comp.on_candle(msg)
      }
  }

}
function onTickerReceived(msg)
{
  if (msg["symbol"] == currentSymbol.value)
  {
      let color = msg["gain"]>=0 ? '#4bffb5' : '#ff4976';  
      //console.log("MultiCandleChartWidget on_ticker",msg) 
      ticker.value= ` Last: <span style='color:yellow'><b> ${msg["last"]} </b></span>  Gain: <span style='color:${color}'><b>${msg["gain"].toFixed(2)} %</b></span>  Vol: ${window.formatValue(msg["day_volume"])}`  ;

      for (const id in widgetRefs.value) {
        const comp = widgetRefs.value[id]
        if (comp)
          comp.onTickerReceived(msg)
      }
  }
}

function onPositionUpdated(msg){
   if (msg.symbol == props.symbol)
   {
      position.value = msg.position
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

watch(
  () => props.symbol,
  async () => {
   // console.log('symbol cambiato:', oldVal, '→', newVal)
    // qui fai quello che ti serve

      let pos_list = await send_get('/account/positions')
      pos_list.forEach(  (val) =>{
            val["type"] = "POSITION"
            onPositionUpdated(val);
      });

  }
)


</script>

<style scoped>


.in-charts-grid {
  width: 100%;
  height: calc(100% - 140px);
  padding: 6px;
  box-sizing: border-box;
  background-color: azure;
  padding-right: 10px;
}
.in-charts-grid > * {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
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
 /* text-align: right ;
  margin-left: auto;*/
  /*align-self: flex-end;*/
}
.trade_console{
  height: 90px;
  border: #0077ff solid    ;
  border-width: 1;
}


.chart-header {
  display: flex;
  flex-direction: row;
  gap: 6px;
  width: 100%;
  height: 60px;
  background-color: #2b2b43;
}

.top-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 600px;
}

.middle-row {
  width: 100%;
  display: flex;
  justify-content: center;
  font-size: 1.1rem;
}

.bottom-row {
  display: flex;
  justify-content: flex-end;
}

.symbol {
  color: yellow;
   font-size: 1.9rem;
}
.positon{
  margin-left: 10px;
    color: rgb(255, 255, 255);
   font-size: 1.9rem;
}
</style>
