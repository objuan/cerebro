<template>
  <div ref="container" class="grid-stack-item-content border rounded bg-dark text-white shadow-sm" >
    <div v-if="!props.multi_mode" class="header grid-stack-handle d-flex justify-content-between align-items-center p-2 bg-secondary bg-opacity-25 border-bottom">
      <div class="d-flex align-items-center"  >
        <span class="me-2">📈</span>
        <strong class="text-uppercase">Single {{ currentSymbol }}</strong>
        <button   class="btn p-0 ms-2" title="Refresh"   @click="handleRefresh" >🔄 </button>
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
      <div class="controls d-flex gap-2">
        <select 
          v-model="currentTimeframe" 
          @change="handleRefresh" 
          class="form-select form-select-sm bg-dark text-white border-secondary timeframe-selector"
        >
          <option value="10s">10s</option>
          <option value="1m">1m</option>
          <option value="5m">5m</option>
          <option value="1h">1h</option>
          <option value="1d">1d</option>
        </select>
        <button @click="$emit('close', id)" class="btn btn-sm btn-outline-light border-0 close-btn">✕</button>
      </div>
    </div>
    <div v-if="props.multi_mode" class="bulk_header" >
        <span>{{ currentTimeframe }}</span>
        <button   class="btn p-0 ms-2" title="Refresh"   @click="handleRefresh" >🔄 </button>
    </div>
    <div class="position-relative flex-grow-1 p-0" style="height: calc(100%-45px ); overflow: hidden;">
      <div class="chart-legend-up  small" v-html="legendHtml"></div>

      <div ref="chartContainer" class="chart-container h-100 w-100 d-flex flex-column">
        <div ref="mainChartRef" class="flex-grow-1 w-100">
          <div class="chart-legend-left-ind  small" v-html="legendIndHtml"></div>
          <div class="chart-legend-left small"  >
                <span class="text-white me-3">Vol: {{  formatValue(lastMainCandle?.volume) }}</span>
              </div>
        </div>
        <div ref="volumeChartRef" style="height: 100px;" class="w-100 border-top border-secondary"></div>

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
  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted ,onBeforeUnmount } from 'vue';
import { liveStore } from '@/components/js/liveStore.js';
//import { createChart, CrosshairMode,  CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { createChart, CrosshairMode,  CandlestickSeries, 
  HistogramSeries, LineSeries,
createInteractiveLineManager  } from '@pipsend/charts'; //createTradingLine
import { eventBus } from "@/components/js/eventBus";

import { formatValue,send_delete,send_get,send_mulo_get } from '@/components/js/utils.js'; // Usa il percorso corretto
import { drawTrendLine,drawHorizontalLine,clearLine,clearDrawings,updateTaskMarker, updateTradeMarker ,setTradeMarker
 } from '@/components/js/chart_utils.js';  // ,onMouseDown,onMouseMove,onMouseUp

const props = defineProps({
  multi_mode: { type: Boolean, default: false },
  id: { type: String, required: true },
  symbol: { type: String, required: true },
  timeframe: { type: String, default: '1m' },
  plot_config: { type: Object, default: () => ({ main_plot: {} }) }
});


const emit = defineEmits(['close', 'initialized']);

// Elementi DOM e Variabili reattive
const mainChartRef = ref(null);
const volumeChartRef = ref(null);
const legendHtml = ref('');
const legendIndHtml = ref('');
const currentTimeframe = ref(props.timeframe);
const currentSymbol = ref(props.symbol);
const symbolList = ref([]);
const container = ref(null);
const price_marker= ref(null);
const price_marker_tp= ref(null);
const price_marker_sl= ref(null);

const gfx_canvas = ref(null);

const drawMode = ref(null); // null | 'hline' | 'line'
let drawPoints = [];
let drawSeries = [];
//let dragging=false;
//let lastMouse=null;

// Oggetti Chart e Series (non reattivi per performance)
let charts = { main: null, volume: null };
let series = { main: null, volume: null, indicators: {} };
let lastMainCandle=null
let tradeData = {}; 
let tradeMarkers = {}

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
        charts,
        series,
        drawSeries,
        liveStore,
        gfx_canvas
    };
}
/*
 --- LOGICA REFRESH DATI ---
*/
const handleRefresh = async () => {
  try {
    console.log("handleRefresh ", props.timeframe);

    // SYMBOLS CANDLES
    const responses = await fetch(`http://127.0.0.1:8000/api/symbols`);
    const datas = await responses.json();
    //console.log("symbols",datas)
    symbolList.value= datas["symbols"];
 
    const response = await fetch(`http://127.0.0.1:8000/api/ohlc_chart?symbol=${currentSymbol.value}&timeframe=${currentTimeframe.value}`);
    const data = await response.json();

    const ind_response = await send_get(`/api/chart/read`,{"symbol":currentSymbol.value,"timeframe":currentTimeframe.value  });
    //ind_response.data = JSON.parse(ind_response.data)
    ind_response.map( line => {
        line.data = JSON.parse(line.data)
    })  

    const task_response = await send_mulo_get(`/order/task/symbol`,{"symbol":currentSymbol.value ,"onlyReady":true});
    console.log("task_response",task_response.data)
    let _task_datas = task_response.data;

     // TRADE MARKER

    const _trade_data = await send_get("/api/trade/marker/read", { "symbol":currentSymbol.value, "timeframe":currentTimeframe.value});
     
      if (_trade_data.data!=null)
        _trade_data.data = JSON.parse(_trade_data.data)
      console.debug("trade marker",_trade_data)
      
    //console.log("ind_response",ind_response) 

    console.debug("loading ",currentSymbol.value,currentTimeframe.value)
    
    if (data && data.length > 0) {
      // Formatta dati per Candlestick
      const formattedData = data.map(d => ({
        time: window.db_localTime ? window.db_localTime(d.t) : d.t,
        open: d.o, high: d.h, low: d.l, close: d.c, volume: d.bv
      }));

      series.main.setData(formattedData);

      // Formatta dati per Volume
      series.volume.setData(data.map(d => ({
        time: window.db_localTime ? window.db_localTime(d.t) : d.t,
        value: d.bv,
        color: d.c >= d.o ? '#4bffb5aa' : '#ff4976aa'
      })));

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
        charts.main.timeScale().setVisibleLogicalRange({
          from: data.length - timeframe_start[currentTimeframe.value],
          to: data.length
        });
      }

      // TRADE MARKER
      if (_trade_data.data!=null)
      {
          tradeData = _trade_data.data;
          updateTradeMarker(context(),tradeData)

          liveStore.updatePathData('trade.tradeData.'+currentSymbol.value, tradeData);
              
      }

      // TASK MARKER

      if (_trade_data.data!=null)
      {
          tradeData = _trade_data.data;
          updateTradeMarker(context(),tradeData)

          liveStore.updatePathData('trade.tradeData.'+currentSymbol.value, tradeData);
              
      }
      if (_task_datas!=null){

         tradeMarkers={}
          _task_datas.forEach( (task)=>
          {
              tradeMarkers["price_marker"] ={"ref" : price_marker, "task": task}
          });
        
        //updateTaskMarker(context(),price_marker,_task_datas)

      }
      
      //console.log("trade marker",data)

      //DEFAULT_INTERACTION = charts.main.options();
    }
  } catch (err) {
    console.error("Errore refresh:", err);
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

     tradeData = {};
     updateTradeMarker(context(),tradeData)
     return;
  }

  drawMode.value = mode;
  drawPoints = [];
  console.log("Draw mode:", mode);
}

const handleSymbols = async () => {
  handleRefresh();
};
const setSymbol = async (symbol) => {
  currentSymbol.value= symbol
  handleRefresh();
};

// =========================

function onOrderReceived(order) {
  if (order.symbol == props.symbol)
  {
    console.debug("Chart → ordine:", order);
  }
}

function onTaskOrderReceived(order){
  if (order.symbol == props.symbol)
  {
     console.log("Chart → task ordine:", order);
     handleRefresh();
   // console.log("Chart → task ordine:", order);
  }
}

// --- INIZIALIZZAZIONE ---
onMounted(() => {

  eventBus.on("order-received", onOrderReceived);
  eventBus.on("task-order-received", onTaskOrderReceived);

  buildChart();
  handleRefresh();
  resize()
});

onBeforeUnmount(() => {
  eventBus.off("order-received", onOrderReceived);
  eventBus.off("task-order-received", onTaskOrderReceived);
});

onUnmounted(() => {

  if (charts.main) charts.main.remove();
  if (charts.volume) charts.volume.remove();
});


function watchPriceScale() {
    if (gfx_canvas.value)
    {
        if (price_marker.value!=null){
            price_marker.value.style.display ="none"
            price_marker_tp.value.style.display ="none"
            price_marker_sl.value.style.display ="none"
          updateTaskMarker(context(),tradeMarkers)
      }
    }
    requestAnimationFrame(watchPriceScale);
  }

watchPriceScale();


/* Full resize for gridstack
*/
const buildChart =  () => {
 //console.log("buildChart")
  // 1. Main Chart
  try{
  charts.main = createChart(mainChartRef.value, {
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

  series.main = charts.main.addSeries(CandlestickSeries, {
    upColor: '#4bffb5', downColor: '#ff4976', borderUpColor: '#4bffb5', borderDownColor: '#ff4976',
    wickUpColor: '#838ca1', wickDownColor: '#838ca1',
  });

  // 2. Volume Chart
  charts.volume = createChart(volumeChartRef.value, {
    height: 100,
    layout: { background: { color: '#131722' }, textColor: '#d1d4dc' },
    timeScale: { visible: false }, // Nascondi scala tempo sotto
    rightPriceScale: { borderVisible: false }
  });

  series.volume = charts.volume.addSeries(HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceScaleId: '',
    scaleMargins: { top: 0.7, bottom: 0 }
  });
 
  // Add SMA (Simple Moving Average) - appears on main chart
  //applySMA(series.main, charts.main, { period: 20, color: '#FFFF00' });
  /*
  const stopLoss = createTradingLine(series.main, charts.main, {
    price: 185.35,
    type: 'stop-loss',
    onDragStart: (price) => console.log('Drag started',price),
    onDragMove: (price) => console.log('Moving:', price),
    onDragEnd: (price) => console.log('Final:', price)
});
*/

    //console.log("stopLoss",stopLoss );

   // Click-to-create: Create lines by clicking on chart
  manager = createInteractiveLineManager( charts.main,series.main);
  console.debug(manager);
  // 3. Indicatori Dinamici
  //console.log("plot_config",props.plot_config)
  if (props.plot_config.main_plot!=null)
  {
    Object.entries(props.plot_config.main_plot).forEach(([key, config]) => {
      if (config.fun === 'ema') {
        series.indicators[key] = charts.main.addSeries(LineSeries, {
          color: config.color,
          lineWidth: 1,
          lastValueVisible: false,
          priceLineVisible: false
        });
      }
    });
  }

  // 4. Sincronizzazione TimeScale
  const mainTimeScale = charts.main.timeScale();
  const volumeTimeScale = charts.volume.timeScale();

  mainTimeScale.subscribeVisibleLogicalRangeChange(range => volumeTimeScale.setVisibleLogicalRange(range));
  volumeTimeScale.subscribeVisibleLogicalRangeChange(range => mainTimeScale.setVisibleLogicalRange(range));

  //charts.main.timeScale().subscribeVisibleTimeRangeChange(updateMarker);
 
  // MOUSE MOVE - CROSSHAIR SYNC + LEGEND UPDATE
  charts.main.subscribeCrosshairMove(param => 
  {
    if (!param.time || !param.seriesData.get(series.main)) {
      legendHtml.value = '';
      legendIndHtml.value = '';
      charts.volume.setCrosshairPosition(0, 0, series.volume); // Clear
      return;
    }

    const data = param.seriesData.get(series.main);
    if (!data) return;

    // update markers
    /*
    const timeScale = charts.main.timeScale();
    const range = timeScale.getVisibleLogicalRange();
    // ultimo indice logico visibile
    const logicalIndex = Math.floor(range.to);
    const x = timeScale.logicalToCoordinate(logicalIndex);
    const y = series.main.priceToCoordinate(184.48);

    console.log("X,Y", price_marker.value,x,y);

    price_marker.value.style.top = `${y - price_marker.value.offsetHeight / 2}px`;
    price_marker.value.style.left = `${x}px`; // asse sinistro
    */
    //updateMarker();
    
    //lastMouse = data;

    // VOLUUME LINK
    charts.volume.setCrosshairPosition(data.value || data.close, param.time, series.volume);
    const bar = series.volume.data().find(x => x.time === param.time);
    const vol = bar?.value;

    //console.log("MOVE ",vol)

    // Update Legend
    let color = data.close >= data.open ? '#4bffb5' : '#ff4976';  
    let lbl = `<span style="color:${color}"> C: <strong>${data.close.toFixed(3)}</strong> O: <strong>${data.open.toFixed(3)}</strong> `;
    lbl += `L: <strong>${data.low.toFixed(3)}</strong> H: <strong>${data.high.toFixed(3)}</strong>`;
    lbl += ` V: <strong>${vol}</strong></span>`;
    legendHtml.value = lbl;

    lbl=""
    // Aggiungi valori indicatori alla legenda
    Object.entries(series.indicators).forEach(([key, s]) => {
      const val = param.seriesData.get(s);
      if (val) lbl += ` <span style="color:${props.plot_config.main_plot[key].color}">${key}: ${val.value.toFixed(3)}</span><br>`;
    });
    
    legendIndHtml.value = lbl;
  });


  charts.main.subscribeClick(param => {
    
    if (!drawMode.value ) return;
    if (!param || !param.point || !param.time) {
      console.log("Click cancelled");
      return;
    }
    //const candle_price = param.seriesData.get(series.main).close;
    const price = series.main.coordinateToPrice(param.point.y);
  
    if (price == null) return;

    console.log("Click at", param.time, price);  
   
    if (drawMode.value === 'hline') {
      drawHorizontalLine(context(),price);
      drawMode.value = null;
    }

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
     if (drawMode.value === 'trade_marker') {
        //tradeData.price = price;
        tradeData.price = price;  
        tradeData.type="bracket"
        setTradeMarker(context(),tradeData)

        drawMode.value = null;

    }

  });

  //
  // Caricamento Iniziale
  //buildChart();
  handleSymbols();
    
  // Esponi l'oggetto al genitore (per aggiornamenti WS)
  emit('initialized', { 
    id: props.id, 
    mainSeries: series.main, 
    volumeSeries: series.volume,
    refresh: buildChart 
  });

  gfx_canvas.value = container.value.querySelector('canvas');
  //console.log(container.value,canvas);
  const canvasParent = gfx_canvas.value.parentElement;
  canvasParent.appendChild(price_marker.value);
  
}catch(ex){
  console.error(ex)
}

};


// =========================

const resize =  () => {
    const { width, height } = container.value.getBoundingClientRect()
    console.debug("c resize ",width,height,container);
   // console.log(charts.main)
   
    charts.main.resize(width-10,height-100);
    charts.volume.resize(width-10,94);
    handleRefresh();
};



function on_candle(c)
{
  //console.log("on_candle",currentTimeframe.value) 
  if (c.tf !== currentTimeframe.value) return;  
  const new_value = {
    time: window.db_localTime(c.ts),
    open: c.o, high: c.h, low: c.l, close: c.c,volume: c.v
  }
  //console.log("new_value",c) 
  if (lastMainCandle !=null && new_value.time >= lastMainCandle.time )
  {
    lastMainCandle =new_value;
    series.main.update(new_value);
    
    series.volume.update({
                time: window.db_localTime(c.ts),
                value: c.v,
                color: c.c >= c.o ? '#4bffb5aa' : '#ff4976aa'
    });  

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
});


</script>

<style scoped>

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
.chart-legend-up{
  left:  50px;
  pointer-events: none;
  background: rgba(19, 23, 34, 0.7);
  border-bottom-right-radius: 4px;
  z-index: 10 !important;
  position: absolute;
}
.chart-legend-left {
  left:  0px;
  bottom: 130px;
  text-align: left;
  pointer-events: none;
  background: rgba(19, 23, 34, 1);
  border-bottom-right-radius: 4px;
  z-index: 10 !important;
  position: absolute;
}
.chart-legend-left-ind {
  left:  0px;
  top: 40px;
  text-align: left;
  pointer-events: none;
  background: rgba(19, 23, 34, 0.7);
  border-bottom-right-radius: 4px;
  z-index: 10 !important;
  position: absolute;
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

</style>
