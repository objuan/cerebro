<template>
  <div ref="container" class=" border rounded bg-dark text-white shadow-sm chart-parent" style="overflow: hidden;" >
    
    <div  class="bulk_header" >
      <div style="display: grid;grid-template-columns: 80px 1fr;">
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
        <button   class="btn p-0 ms-2" title="Refresh"   @click="handleRefresh" >🔄 </button>
      </div>
    </div>

    <!---   -->
    <div class="position-relative p-0 chart-panel">
      <div class="chart-legend-up  small" v-html="legendHtml"></div>

      <!--<canvas ref="bgCanvas" class="bg-overlay"></canvas>-->

      <div ref="chartContainer" class="chart-container  w-100 d-flex flex-column">
        <div ref="mainChartRef" class=" w-100" >
          
           <!-- TODO aggiungere FLOAT, MARKETCAP -->
           <!-- INDICATOR MENU -->

          <div class="chart-legend-left-ind">

              <DropdownMenu
              label="="
              :items="menuItems"
              @select="handleMenu"
            />
            
            <DropdownMenu
              :label="profileName"
              :items="menu_indicatorList"
              @select="selectProfile"
            />
            

            <!-- INDICATOR LEGENDS -->

            <div
              class="chart-legend-left-ind-item"
              v-for="(ind, i) in indicatorList"
              :key="ind.id || i"
            >
              <span :style="{ color: ind.params.color }">
                {{ ind.name }}
              </span>

              <input
                type="color"
                v-model="ind.params.color"
                class="ms-0 p-0 b-0"
                style="width:20px;height:20px"
                @input="updateIndicatorColor(ind)"
              />

              <button
                class="btn btn-sm btn-outline-danger ms-0 p-0 b-0" 
                
                style="width:20px;height:20px"
                @click="removeIndicator(i)"
                title="Rimuovi indicatore"
              >
                ✕
              </button>
            </div>
          </div>

        </div>

    
        <!-- BUTTON BAR -->

        <div class="button_bar">
          <button   class="btn btn-sm btn-outline-warning ms-2"   title="Horizontal line"
            @click="setDrawMode('hline')">
            ─
          </button>

          <button  class="btn btn-sm btn-outline-warning ms-1"  title="Trend line" 
              @click="setDrawMode('line')">
            ／
          </button>

          <button  class="btn btn-sm btn-outline-danger ms-1"  title="Clear drawings"
            @click="setDrawMode('delete')">
            D
          </button>

          <button  class="btn btn-sm btn-outline-danger ms-1"  title="Clear drawings"
            @click="setDrawMode('delete_all')">
            ✕
          </button>
    
          
        </div>

        <!-- TRADE BAR -->
        <div class="trade_bar">
            <button   class="btn btn-sm btn-outline-warning ms-2"   title="Set Trade"
              @click="setDrawMode('trade_marker')" 
              @pointerdown.stop
              @pointerup.stop
              @mousedown.stop
              @mouseup.stop
              @click.stop>
              +
            </button>

            <button  class="btn btn-sm btn-outline-danger ms-1"  title="Delete Trade"
              @click="setDrawMode('trade_delete')">
              ✕
            </button>

        </div>
       
      </div>
    </div>
    <div ref="price_marker" class="price-marker">
      <span class="icon">🎯</span>
   </div>
   <div  ref="price_marker_tp" class="price-marker">
      <span class="icon">🏁</span>
   </div>
   <div  ref="price_marker_sl" class="price-marker">
      <span class="icon">⛔</span>
   </div>
   <CandleChartIndicator ref="indicatorMenu"
        @add-indicator="onAddIndicator"></CandleChartIndicator>


  </div>

  
</template>


<script setup>
import { ref, onMounted, onUnmounted ,onBeforeUnmount,toRaw,computed, nextTick } from 'vue';
import { liveStore } from '@/components/js/liveStore.js';
import { staticStore } from '@/components/js/staticStore.js';
import  CandleChartIndicator  from '@/components/CandleChartIndicator.vue'
//import { createChart, CrosshairMode,  CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { createChart, CrosshairMode,  CandlestickSeries, 
   LineSeries, applyVolume,setVolumeData,updateVolumeData,
createInteractiveLineManager ,LineStyle } from '@/components/js/ind.js' // '@pipsend/charts'; //createTradingLine

import { eventBus } from "@/components/js/eventBus";
import { send_delete,send_get,saveProp, send_post } from '@/components/js/utils.js'; // Usa il percorso corretto
import { drawTrendLine,drawHorizontalLine,clearLine,clearDrawings,updateTaskMarker,
   updateTradeMarker ,setTradeMarker,updateVerticalLineData,findLastCandleOfEachDay,findOpenDate
 } from '@/components/js/chart_utils.js';  // ,onMouseDown,onMouseMove,onMouseUp
import DropdownMenu from '@/components/DropdownMenu.vue';
import { tradeStore } from "@/components/js/tradeStore";

const props = defineProps({
  id: { type: String, required: true },
  number: { type: Number, required: true },
  grid: { type: String, required: true },
  sub_number: { type: Number, required: true },
  symbol: { type: String, required: true },
  timeframe: { type: String, default: '1m' },
  plot_config: { type: Object, default: () => ({ main_plot: {} }) }
});


const emit = defineEmits(['close', 'initialized']);

// Elementi DOM e Variabili reattive
const indicatorMenu = ref(null);
const mainChartRef = ref(null);
const legendHtml = ref('');
//const legendIndHtml = ref('');
const currentTimeframe = ref(props.timeframe);
const currentSymbol = ref(props.symbol);
//const symbolList = ref([]);
const container = ref(null);
const price_marker= ref(null);
const price_marker_tp= ref(null);
const price_marker_sl= ref(null);
const indicatorList = ref([]);
const profileName = ref("");
let timeLine_pre=null;
let timeLine_open=null;

const gfx_canvas = ref(null);

const drawMode = ref(null); // null | 'hline' | 'line'
let drawPoints = [];
let drawSeries = [];

// Oggetti Chart e Series (non reattivi per performance)
//let charts = { main: null, volume: null };
//let series = { main: null, volume: null, indicators: {} };
let chart = null;
let series  = null;
let buy_line = null
//let indicators = {}

let lastMainCandle=null
let tradeMarkerData = {}; 
let taskData = {}

//let DEFAULT_INTERACTION=null;
let manager = null;


let timeframe_start = {}
timeframe_start["10s"] = 100
timeframe_start["1m"] = 50
timeframe_start["5m"] = 50
timeframe_start["1h"] = 24
timeframe_start["1d"] = 30

function context() {
    return {
        currentSymbol,
        currentTimeframe,
        chart,
        series,
        drawSeries,
        liveStore,
        gfx_canvas
    };
}

const lastTrade = computed(() => {
  return tradeStore.lastTrade(props.symbol);
})
console.log("lastTrade",lastTrade.value)  

const get_layout_key = (subkey)=> { return `chart.${props.number}.${props.grid}.${props.sub_number}.${subkey}`}
const get_indicator_key = ()=> { return `chart.${props.number}.indicator.${currentTimeframe.value}`}

function onTimeFrameChange(){
 // console.log("onTimeFrameChange")
  
  saveProp(get_layout_key("timeframe"), currentTimeframe.value)
  staticStore.set(get_layout_key("timeframe"), currentTimeframe.value)
  //profileName=""
  let ind_profile = staticStore.get(get_indicator_key(),null)
  if (ind_profile)
          {
            console.log("ind_profile",get_indicator_key())
            nextTick(  loadIndicators(ind_profile))
         
          }
          else
            clearIndicators()

  handleRefresh();
}

// ===============================

const linkName = computed(() => `Link to slot:${props.number} tf: ${currentTimeframe.value}`);

const menu_indicatorList = []
const profile_indicatorList=[]

const menuItems = [
  { key: 'add', text: 'Add Indicator' },
  { key: 'save', text: 'Save' },
  { key: 'load', text: 'Load' },
  { key: 'link', text: linkName },
  { key: 'link_clear', text: "Link Clear" }
];
//console.log(menuItems)


async function handleMenu(item) {
 
  if (item.key === 'add') openIndicatorMenu();
  if (item.key === 'save') saveIndicators();
  if (item.key === 'load') await loadIndicators(null);
  if (item.key === 'link') linkIndicators();
  if (item.key === 'link_clear') linkClearIndicators();
}


async function selectProfile(item) {
 // console.log("...",item)
  clearIndicators()
  if (item!=null)
  {
    let index=-1;
    for(let idx = 0;idx < profile_indicatorList.length;idx++)
    {
        if (profile_indicatorList[idx].name ==item.text )
          index = idx
    }
    if (index!= -1)
      getIndicators(profile_indicatorList[index])
    
  }
}

// ===================================

function onAddIndicator(ind){
    let serie = indicatorMenu.value.addIndicator(context(),ind)
   // console.log("add",serie)
    indicatorList.value.push(serie)
}

function openIndicatorMenu(){
  indicatorMenu.value.open();
}

function getIndicators(profile)
{   
  profileName.value = profile.name
 // console.log("getIndicators",profile)
  profile.data.forEach( (ind)=>{
      onAddIndicator(ind)
  })
}

function updateIndicatorColor(ind) {
  if (ind.serie) {
    ind.serie.applyOptions({
      color: ind.params.color
    });
  }
}

// ------

async function loadIndicators(profileName)
{
  /*
  let list = await send_get("/api/chart/indicator/list")
  list.forEach(line => {
      line.data = JSON.parse(line.data);
  });
  if (!list.length) {
    alert("Nessun set di indicatori salvato.");
    return;
  }
    */

 // console.log("loadIndicators",profileName)

  let index=null;
  /*
  if (profileName==null)
  {
      // Crea elenco numerato
      const optionsText = list
        .map((l, i) => `${i + 1}) ${l.name}`)
        .join("\n");

      const choice = prompt(
        "Scegli quale set caricare:\n\n" + optionsText
      );

      if (!choice) return;

      index = parseInt(choice, 10) - 1;

      if (isNaN(index) || index < 0 || index >= list.length) {
        alert("Scelta non valida");
        return;
      }

    }
    else*/
    {
       for(let idx = 0;idx < profile_indicatorList.length;idx++)
       {
          if (profile_indicatorList[idx].name ==profileName )
              index = idx
       }
 
      //console.log("FIND ",index)
    }
  
    clearIndicators()

    if (index!=null)
    {
      

      const selected = profile_indicatorList[index];

     // console.log("Load Profile:", selected.name, selected.data);

      //let key = get_layout_key(`indicator.${selected.name}`)

      getIndicators(selected)
      // QUI assegni gli indicatori
      // es:
      // this.indicatorList = selected.data
    }

  //  console.log("loadIndicators","DONE")
}

function saveIndicators(){

  if (indicatorList.value.length==0)
    return;

  const name = window.prompt("Nome per salvare gli indicatori:");

  if (!name) return; // annullato o vuoto

  // qui fai quello che ti serve con il nome
  //console.log("Salvo con nome:", name);
  let data=[]
  indicatorList.value.forEach((ind) => {
    data.push({"type" : ind.type ,"params" : ind.params})
  });
   //console.log("data",data)

   send_post("/api/chart/indicator/save", {"name": name, "data":data })
}

function removeIndicator(index) {

    const ind = toRaw(indicatorList.value[index]);

   // console.log("Remove",index, "len",indicatorList.value.length)
    //indicatorList.value.splice(index, 1)
    indicatorList.value = indicatorList.value.filter((_, i) => i !== index);

    //console.log("Remove",ind.serie)

    if (ind.serie.isComposite)
      {
        chart.removeSeries(ind.serie.macd);
        chart.removeSeries(ind.serie.signal);
        chart.removeSeries(ind.serie.histogram);
      }
    else
      chart.removeSeries(ind.serie)
}
function clearIndicators(){
  profileName.value=""
    while(indicatorList.value.length>0)
          removeIndicator(0)
}
function linkIndicators(){
    if (profileName.value=="")
      return

     send_post('/api/props/save', { path: get_indicator_key(), "value": profileName.value });
}
function linkClearIndicators(){
    send_post('/api/props/save', { path: get_indicator_key(), "value": "" });
    clearIndicators();
}
//  ---------
/*
 --- LOGICA REFRESH DATI ---
*/
const handleRefresh = async () => {
  try {
    //console.log("handleRefresh ", currentTimeframe.value);

    // SYMBOLS CANDLES

 
    const response = await fetch(`http://127.0.0.1:8000/api/ohlc_chart?symbol=${currentSymbol.value}&timeframe=${currentTimeframe.value}`);
    
    const data = await response.json();
    //console.log("response",data)

    if (data.length>0)
    {
      const ind_response = await send_get(`/api/chart/read`,{"symbol":currentSymbol.value,"timeframe":currentTimeframe.value  });
      //ind_response.data = JSON.parse(ind_response.data)
      ind_response.map( line => {
          line.data = JSON.parse(line.data)
      })  

      // TASK LIST

      const task_response = await send_get(`/order/task/symbol`,{"symbol":currentSymbol.value ,"onlyReady":true});
      //console.log("task list",task_response.data)
      let _task_datas = task_response.data;

      // TRADE MARKER

      const _trade_marker_data = await send_get("/api/trade/marker/read", { "symbol":currentSymbol.value, "timeframe":currentTimeframe.value});
      
      if (_trade_marker_data.data!=null)
          _trade_marker_data.data = JSON.parse(_trade_marker_data.data)
      console.debug("trade marker",_trade_marker_data)
        
      //console.log("ind_response",ind_response) 

      console.debug("loading ",currentSymbol.value,currentTimeframe.value)
      
      if (data && data.length > 0) {

        const formattedData = data.map(d => ({
          time: window.db_localTime ? window.db_localTime(d.t) : d.t,
          open: d.o, high: d.h, low: d.l, close: d.c, volume: d.bv
        }));

        //console.info("formattedData ",data)

        series.setData(formattedData);

        // OPEN DATE

        updateVerticalLineData(timeLine_pre,formattedData,findLastCandleOfEachDay(formattedData))
      updateVerticalLineData(timeLine_open,formattedData,findOpenDate(formattedData))


        lastMainCandle = formattedData[formattedData.length - 1];

        // Gestione Indicatori (EMA, etc)
        if (props.plot_config.main_plot!=null)
        {
          Object.entries(props.plot_config.main_plot).forEach(([key, config]) => {
            if (config.fun === 'ema' && window.calculateEMA) {
              const indData = window.calculateEMA(data, config.eta);
              series.indicators[key].setData(indData);
            }
          });
        }

        // gestione lieen user
        clearDrawings( context() );
        ind_response.forEach( line =>
        {
            if (line.type ==='price_line')
            {
                drawHorizontalLine(context(),line.data.price, line.guid);
            }
            if (line.type ==='trend')
            {
              // console.log("draw trend",line.data)
                drawTrendLine(context(),line.data.p1,line.data.p2, line.guid);
            }
        });


        // Zoom finale
        
        if ( data.length >timeframe_start[currentTimeframe.value])
        {
          try{
            chart.timeScale().setVisibleLogicalRange({
              from: data.length - timeframe_start[currentTimeframe.value],
              to: data.length
            });
          }catch{
            console.debug("!!")
          }
        }
          
        // chart.timeScale().scrollToPosition(0, false);
        nextTick( ()=>
      {
                setVolumeData(series,data.map(d => ({
                  time: window.db_localTime ? window.db_localTime(d.t) : d.t,
                  volume: d.bv,
                  color: d.c >= d.o ? '#4bffb5aa' : '#ff4976aa'
                })));
      } );
 

        // TRADE MARKER
        if (_trade_marker_data.data!=null)
        {
            tradeMarkerData = _trade_marker_data.data;
            updateTradeMarker(context(),tradeMarkerData)

            liveStore.updatePathData('trade.tradeData.'+currentSymbol.value, tradeMarkerData);
                
        }
 
        // TRADE MARKER
        if (_task_datas!=null){

            taskData={}
            _task_datas.forEach( (task)=>
            {
              const next_step_idx = task.step;
              const data = JSON.parse(task.data)

              //console.log("..",next_step_idx,data)

              // prendo i passi prima
              data.forEach( (step)=>
              {
                  if (step["step"]== next_step_idx)
                  {
                    console.log("ACTIVE",step)
                    if (step["desc"] == "MARKER")
                        taskData["price_marker"] ={"ref" : price_marker, "task": step}
                    if (step["desc"] == "SL")
                        taskData["price_marker_sl"] ={"ref" : price_marker_sl, "task": step}
                    if (step["desc"] == "TP")
                        taskData["price_marker_tp"] ={"ref" : price_marker_tp, "task": step}
                  }
              });
            });
        }

        // INDICATORS

          let ind_profile = staticStore.get(get_indicator_key(),null)
          if (ind_profile)
          {
          //  console.log("ind_profile",get_indicator_key())
            nextTick(  loadIndicators(ind_profile))
         
          }
          else
            clearIndicators()

          // LAST TRADE
          console.log("buy_line",buy_line)  
          if (buy_line!=null)
          {
            series.removePriceLine(buy_line);
            //chart.removePriceLine(buy_line);
            buy_line=null
          }
          if(lastTrade.value != null  && lastTrade.value.isOpen)
          {
            
              buy_line = series.createPriceLine({
                    price: lastTrade.value.list[0].price  ,
                    color: '#00ff00',
                    lineWidth: 1,
                    lineStyle: LineStyle.SparseDotted, // oppure Dashed
                    axisLabelVisible: true,
                    title: 'BUY'
                  });
              console.log("buy_line ADD",buy_line)  
          }
          
          
      }
      //console.log("trade marker",data)

      //DEFAULT_INTERACTION = chart.options();

    
     console.log("handleRefresh DONE")
    }
    else
        console.log("empty ");
  } catch (err) {
    console.debug("Errore refresh:", err.stack);
  }
};


// UI LINKS

async function setDrawMode(mode) {
  if (mode === 'delete_all') {
    clearDrawings(context(),true);
    return;
  }
  if (mode === 'trade_delete') {

     let ret = await send_delete("/api/trade/marker/delete", { "symbol":currentSymbol.value, "timeframe":currentTimeframe.value}); 
     console.log("trade delete",ret)  

     tradeMarkerData = {};
     updateTradeMarker(context(),tradeMarkerData)
     return;
  }

  drawMode.value = mode;
  drawPoints = [];
  console.log("Draw mode:", mode);
}
/*
const handleSymbols = async () => {
   console.log("handleSymbols")
  handleRefresh();
};
*/

const setSymbol = async (symbol) => {
  console.log("setSymbol")
  currentSymbol.value= symbol
  handleRefresh();
};

// =========================

function onOrderReceived(order) {
  if (order.symbol == props.symbol)
  {
  //  console.debug("Chart → ordine:", order);
  }
}

function onTaskOrderReceived(order){
  if (order.symbol == props.symbol)
  {
    // console.log("Chart → task ordine:", order);
     handleRefresh();
   // console.log("Chart → task ordine:", order);
  }
}

function onTradeLastUpdated(msg){
  
 if (msg && msg.symbol === props.symbol)
  {
    //console.log("onTradeLastUpdated ",props.symbol,msg) 
     handleRefresh();
     // tradeStore.push(msg)
  }   
}


// --- INIZIALIZZAZIONE ---
onMounted(  () => {

 // console.log("onMounted")
  //canvas = bgCanvas.value
  //ctx = canvas.getContext('2d')
  //console.log("ctx",canvas,ctx,bgCanvas)

  eventBus.on("order-received", onOrderReceived);
  eventBus.on("task-order-received", onTaskOrderReceived);
  eventBus.on("trade-last-changed", onTradeLastUpdated);

  fetch("http://127.0.0.1:8000/api/chart/indicator/list")
  .then(res => res.json())
  .then(list => {
    //console.log("list", list )
     menu_indicatorList.push({"text" :"------" ,"data" : null })
    list.forEach(line => {
        line.data = JSON.parse(line.data);
        profile_indicatorList.push(line)
        //console.log("INDICASTORS", line.data )
        menu_indicatorList.push({"text" :line.name,"data" : line.data })
    });
     
  });
  

  buildChart();
 // handleRefresh();
  resize()

  onTradeLastUpdated(lastTrade.value  )
});

onBeforeUnmount(() => {
  eventBus.off("order-received", onOrderReceived);
  eventBus.off("task-order-received", onTaskOrderReceived);
  eventBus.off("trade-last-changed", onTradeLastUpdated);
});

onUnmounted(() => {

  if (chart) chart.remove();
  //if (charts.volume) charts.volume.remove();
});

function watchPriceScale() {
    if (gfx_canvas.value)
    {
        if (price_marker.value!=null){
            price_marker.value.style.display ="none"
            price_marker_tp.value.style.display ="none"
            price_marker_sl.value.style.display ="none"
          updateTaskMarker(context(),taskData)
      }
    }
    requestAnimationFrame(watchPriceScale);
  }

watchPriceScale();


/* buildChart
*/
const buildChart =  () => {

  // 1. Main Chart
  try{
  chart = createChart(mainChartRef.value, {
    layout: { background: { color: '#131722' }, textColor: '#d1d4dc' },
    grid: { vertLines: { color: '#2b2b43' }, horzLines: { color: '#2b2b43' } },
    crosshair: { 
      mode: CrosshairMode.Normal,
      horzLine: {
            visible: false,
        }, 
    },
    timeScale: { timeVisible: true, borderColor: '#485c7b' }
  });

  series = chart.addSeries(CandlestickSeries, {
    upColor: '#4bffb5', downColor: '#ff4976', borderUpColor: '#4bffb5', borderDownColor: '#ff4976',
    wickUpColor: '#838ca1', wickDownColor: '#838ca1',
  });

  timeLine_pre =  chart.addSeries(LineSeries, {
    color: '#FFFFFF',
    lineWidth: 2,
    lineStyle:2,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
  timeLine_open =  chart.addSeries(LineSeries, {
    color: '#FFFF00',
    lineWidth: 2,
    lineStyle:2,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });

  // ==============

  applyVolume(series, chart, {
      colorUp: '#26a69a',
      colorDown: '#ef5350'
  });

    let panes = chart.panes();
    //panes[0]?.setHeight(0.1);
    panes[1]?.setStretchFactor(0.5);


    //console.log("stopLoss",stopLoss );

   // Click-to-create: Create lines by clicking on chart
  manager = createInteractiveLineManager( chart,series);
  console.debug(manager);
  // 3. Indicatori Dinamici
  //console.log("plot_config",props.plot_config)
  if (props.plot_config.main_plot!=null)
  {
    Object.entries(props.plot_config.main_plot).forEach(([key, config]) => {
      if (config.fun === 'ema') {
        series.indicators[key] = chart.addSeries(LineSeries, {
          color: config.color,
          lineWidth: 1,
          lastValueVisible: false,
          priceLineVisible: false
        });
      }
    });
  }

  // MOUSE MOVE - CROSSHAIR SYNC + LEGEND UPDATE
  chart.subscribeCrosshairMove(param => 
  {
    try{
      if (!param.time || !param.seriesData.get(series)) {
        legendHtml.value = '';
        //legendIndHtml.value = '';
       // charts.volume.setCrosshairPosition(0, 0, series.volume); // Clear
        return;
      }

      const data = param.seriesData.get(series);
      if (!data) return;

      // update markers
      /*
      const timeScale = chart.timeScale();
      const range = timeScale.getVisibleLogicalRange();
      // ultimo indice logico visibile
      const logicalIndex = Math.floor(range.to);
      const x = timeScale.logicalToCoordinate(logicalIndex);
      const y = series.priceToCoordinate(184.48);

      console.log("X,Y", price_marker.value,x,y);

      price_marker.value.style.top = `${y - price_marker.value.offsetHeight / 2}px`;
      price_marker.value.style.left = `${x}px`; // asse sinistro
      */
      //updateMarker();
      
      //lastMouse = data;

      // VOLUUME LINK
      
      //charts.volume.setCrosshairPosition(data.value || data.close, param.time, series.volume);
      //const bar = series.volume.data().find(x => x.time === param.time);
      //const vol = bar?.value;
      const vol =0;
      

      //console.log("MOVE ",vol)

      // Update Legend
      let color = data.close >= data.open ? '#4bffb5' : '#ff4976';  
      let lbl = `<span style="color:${color}"> C: <strong>${data.close.toFixed(3)}</strong> O: <strong>${data.open.toFixed(3)}</strong> `;
      lbl += `L: <strong>${data.low.toFixed(3)}</strong> H: <strong>${data.high.toFixed(3)}</strong>`;
      lbl += ` V: <strong>${vol}</strong></span>`;
      legendHtml.value = lbl;

      lbl=""
      // Aggiungi valori indicatori alla legenda

      /*
      console.log("indicatorList.value",indicatorList.value)
      Object.entries(indicatorList.value).forEach(([key, s]) => {
        const val = param.seriesData.get(s);
        if (val) lbl += ` <span style="color:${props.plot_config.main_plot[key].color}">${key}: ${val.value.toFixed(3)}</span><br>`;
      });
      
      legendIndHtml.value = lbl;
      */
    }catch(ex){
      console.debug(ex.stack);
    }
    
  });


  chart.subscribeClick(param => {
    
    if (!drawMode.value ) return;
    console.log(param)
    if (!param || !param.point ) {
      console.log("Click cancelled");
      return;
    }
    //const candle_price = param.seriesData.get(series).close;
    const price = series.coordinateToPrice(param.point.y);
  
    if (price == null) return;

    console.log("Click at", param.time, price);  
   
    if (drawMode.value === 'hline') {
      drawHorizontalLine(context(),price);
      drawMode.value = null;
    }
    if (param.time)
    {
      if (drawMode.value === 'line') {
        drawPoints.push({ time: param.time, value: price });

        if (drawPoints.length === 2) {
          drawTrendLine(context(),drawPoints[0], drawPoints[1]);
          drawPoints = [];
          drawMode.value = null;
        }
      }
      if (drawMode.value === 'delete') {
          clearLine(context(),param.time,price)
          drawMode.value = null;
      }
    }
     if (drawMode.value === 'trade_marker') {
        //tradeData.price = price;
        tradeMarkerData.price = price;  
        tradeMarkerData.type="bracket"
        setTradeMarker(context(),tradeMarkerData)

        drawMode.value = null;

    }

  });

  //
  // Caricamento Iniziale
  //buildChart();
  //handleSymbols();
    
  // Esponi l'oggetto al genitore (per aggiornamenti WS)
  emit('initialized', { 
    id: props.id, 
    mainSeries: series, 
    //volumeSeries: series.volume,
    refresh: buildChart 
  });

  gfx_canvas.value = container.value.querySelector('canvas');
  //console.log(container.value,canvas);
  const canvasParent = gfx_canvas.value.parentElement;
  canvasParent.appendChild(price_marker.value);
  canvasParent.appendChild(price_marker_sl.value);
  canvasParent.appendChild(price_marker_tp.value);
  
}catch(ex){
  console.error(ex)
}

};

// =========================
let old_size = [0,0]

const resize =  () => {
    const { width, height } = container.value.getBoundingClientRect()
    if (old_size[0] != width || old_size[1] != height )
    {
      old_size = [ width, height ]

      chart.resize(width-10,height-20);

      handleRefresh();
    }
};


function onTickerReceived(){

}

function on_candle(c)
{
  //
  if (c.tf !== currentTimeframe.value) return;  

  // console.log("on_candle",currentSymbol.value,currentTimeframe.value,c) 

  const new_value = {
    time: window.db_localTime(c.ts),
    open: c.o, high: c.h, low: c.l, close: c.c
  }
  //console.log("new_value",c) 
  if (lastMainCandle !=null && new_value.time >= lastMainCandle.time )
  {
    lastMainCandle =new_value;
    
    updateVolumeData(series,{
                time: window.db_localTime(c.ts),
                volume: c.v
    })

    series.update(new_value);
  

  }
  else
  {
    console.warn("Candle skipped" ) 
  } 
}

// ==========================

defineExpose({
  resize,
  setSymbol,
  on_candle,
  onTickerReceived

});


</script>

<style scoped>

.charts-grid {
  width: 100%;
  height: 100%;
  padding: 6px;
  box-sizing: border-box;
  background-color: azure;
  padding-right: 10px;
}
.charts-grid > * {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}


.price-marker {
  position: absolute;
  align-items: center;
  background: transparent;
  pointer-events: none;
  color: white;
  z-index: 100 !important;
    font-size: 14px;   /* prova 16 / 20 / 24 */
     line-height: 1;
}

.timeframe{
  font-weight: 700;
}
.chart-parent {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chart-panel{
  
  /*height: calc(100% - 45px);*/
  flex: 1;
  overflow: hidden;
}
.chart-legend-up{
  left:  130px;
  pointer-events: none;
  background: rgba(19, 23, 34, 0.7);
  border-bottom-right-radius: 4px;
  z-index: 10 !important;
  position: absolute;
}
.chart-legend-left-bottom {
  left:  0px;
  bottom: 130px;
  text-align: left;
  pointer-events: none;
  background: rgba(19, 23, 34, 1);
  border-bottom-right-radius: 4px;
  z-index: 10 !important;
  position: absolute;
}

.chart-legend-left-ind  {
  left:  0px;
  top: 60px;
  text-align: left;
  background: rgba(50, 59, 85, 0.7);
  border-bottom-right-radius: 4px;
  z-index: 20 !important;
  position: absolute;
  display: flex;
  flex-direction: column  !important;  /* ← verticale */
  gap: 6px;                /* spazio tra elementi */
  align-items: flex-start;              /* spazio tra elementi */
}

.chart-legend-left-ind-item {
  font-size: 0.8em;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.legend-remove-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color:white;
    z-index: 1000 !important;
}


.timeframe-selector {
  width: auto;
  padding: 0 0.5rem;
}
.bulk_header{
  position:absolute;
  z-index: 20 !important;
  font-weight: 300;
  font-size: medium;
  background-color: rgb(0, 0, 0);
  border: white 1px solid ;
  border-radius: 5px;
  padding: 3px;
}
.button_bar{
  position:absolute;
  top:0px;
  left:400px;
  z-index: 20 !important;
  font-weight: 300;
  font-size: medium;
  padding: 3px;
}
.trade_bar{
  position:absolute;
  bottom:145px;
  left:100px;
  z-index: 20 !important;
  font-weight: 300;
  font-size: medium;
  padding: 3px;
}
.bg-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 100;
  display: none;

}
</style>
