<template>
  <div ref="multi_container" @mousedown="handleSelect" class="border rounded bg-dark text-white shadow-sm">
    <div class="chart-header">

        <div class="bottom-row">
            {{ currentSymbol }}
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
        <TradeConsole ref="console" :symbol="currentSymbol"  :liveMode="false"></TradeConsole> 
    </div>

  
    <div class="in-charts-grid" :style="gridStyle">
          <BackChartWidget
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
              @refresh ="on_data_loaded"
          >
          </BackChartWidget>
    </div>
    <BackController ref="controller"
      @update:current="onTimeChange"
    ></BackController>
    


  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted,onBeforeUnmount,nextTick,watch } from 'vue';
import BackChartWidget from './BackChartWidget.vue';
import BackController from './BackController.vue';
import TradeConsole from '../TradeConsole.vue';


import { computed } from 'vue'; // toRaw
import { staticStore } from '@/components/js/staticStore.js';
import {timeframeToSeconds} from '@/components/js/utils.js';

const props = defineProps({
  id: { type: String, required: true },
  symbol : { type: String, required: true, default: null },
  number: { type: Number, required: true },
  timeframe: { type: String, required: false ,default:"10s"},
});

const widgetRefs = ref({})
const console = ref(null)

// Elementi DOM e Variabili reattive

const currentSymbol = computed(() => props.symbol)

const currentLayout= ref("")  
const rows = ref(1)
const cols = ref(1)
const cells = ref([])  // contiene i widget attivi
const controller = ref(null)

let data= []

const emit = defineEmits(['select'])

function onTimeChange(time) {
   for (const id in widgetRefs.value) {
        const comp = widgetRefs.value[id]
        const el = comp?.$el
        if (!el) continue
 
        comp.setBackTime(time);
        
   }

  //console.log("Current time:", date)
}

function handleSelect() {
  emit('select', props.id)
}

const get_layout_key = (subkey)=> { return `back.${props.number}.${subkey}`}

// -------------

const grid = computed( ()=>{
  return `${rows.value}_${cols.value}`
})

const gridStyle = computed(() => ({
  display: 'grid',
  width: '100%',
  //height: '100%',
  height: 'calc(100% - 200px)',
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
  
  staticStore.set(get_layout_key("grid"),grid.value);
  //saveProp(get_layout_key("grid"),grid.value );

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
  staticStore.set(get_layout_key("symbol"), currentSymbol.value); 
};

function on_data_loaded(val){
  
  data =val.data
  //console.log(data)
  //console.log("dt_start",dt_start.value,dt_end.value, timeframeToSeconds(props.timeframe))
  controller.value.setup(data,timeframeToSeconds(props.timeframe),10);

}

// --- INIZIALIZZAZIONE ---
onMounted( async() => {
 // console.log("onMounted");
    currentSymbol.value = props.symbol;
    // --------------
    currentLayout.value = staticStore.get(get_layout_key("grid"),"1_1")

    onChangeLayouts()
});

onBeforeUnmount(() => {

});


const setSymbol = async (symbol) => {
  currentSymbol.value = symbol
  onChangeSymbols()
};

const resize =  () => {
   
    //console.log("m resize ");

    for (const id in widgetRefs.value) {
        const comp = widgetRefs.value[id]
        const el = comp?.$el
        if (!el) continue
        const rect = el.getBoundingClientRect()
        comp.resize(rect.width, rect.height)
   }

};

onUnmounted(() => {
 
});

defineExpose({
  resize,
 
  setSymbol
});

watch(() => props.symbol, () => {

   for (const id in widgetRefs.value) {
        const comp = widgetRefs.value[id]
        const el = comp?.$el
        if (!el) continue
        comp.setSymbol(props.symbol,props.timeframe)
   }

})
watch(() => props.timeframe, () => {
 
   for (const id in widgetRefs.value) {
        const comp = widgetRefs.value[id]
        const el = comp?.$el
        if (!el) continue
        comp.setSymbol(props.symbol,props.timeframe)
       // console.setSymbol(props.symbol.value)
   }
})

</script>

<style scoped>

.time-bar{
  position:relative;
  left:0;
  bottom:0;
  width:100%;
  height:2px;
  background:#525151;
}

.time-bar-fill{
  height:100%;
  width:0%;
  background:#00ff88;
  transition:width .2s linear;
}
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
  height: 100px;
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
  width: 700px;
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
   font-size: 1.5rem;
}
.positon{
  margin-left: 10px;
    color: rgb(255, 255, 255);
   font-size: 1.5rem;
}
</style>
