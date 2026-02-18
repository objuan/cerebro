<template>
  <div ref="container" class=" border rounded bg-dark text-white shadow-sm chart-parent" style="overflow: hidden;" >
    
    <div  class="bulk_header" >
      <div style="display: grid;grid-template-columns: 80px 1fr;">
        {{ timeframe }}
        <button   class="btn p-0 ms-2" title="Refresh"   @click="handleRefresh" >🔄 </button>
      </div>
    </div>

    <!---   -->
    <div class="position-relative p-0 chart-panel">
      <div class="chart-legend-up  small" v-html="legendHtml"></div>

      <!--<canvas ref="bgCanvas" class="bg-overlay"></canvas>-->

      <div ref="chartContainer" class="chart-container  w-100 d-flex flex-column">
        <div ref="mainChartRef" class=" w-100" >
          
        </div>
       
      </div>
    </div>

  </div>

</template>


<script setup>
import { ref, onMounted, onUnmounted ,onBeforeUnmount } from 'vue';

//import  CandleChartIndicator  from '@/components/CandleChartIndicator.vue'
//import { createChart, CrosshairMode,  CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { createChart, CrosshairMode,  CandlestickSeries, 
   applyVolume,setVolumeData,getVolume, // LineSeries
  } from '@/components/js/ind.js' // '@pipsend/charts'; //createTradingLine

import {  formatValue } from '@/components/js/utils.js'; // Usa il percorso corretto
import {

 } from '@/components/js/chart_utils.js';  // ,onMouseDown,onMouseMove,onMouseUp
//import DropdownMenu from '@/components/DropdownMenu.vue';

const props = defineProps({
  id: { type: String, required: true },
  symbol: { type: String, required: true },
  timeframe: { type: String, default: '1m' }
});


// Elementi DOM e Variabili reattive

const mainChartRef = ref(null);
const legendHtml = ref('');
//const legendIndHtml = ref('');
const currentTimeframe = ref(props.timeframe);
const currentSymbol = ref(props.symbol);
//const symbolList = ref([]);
const container = ref(null);

let chart = null;
let series  = null;

//  ---------
/*
 --- LOGICA REFRESH DATI ---
*/
const handleRefresh = async () => {
  try {
    console.log("handleRefresh ",currentSymbol.value, currentTimeframe.value);

    // SYMBOLS CANDLES
    if (currentSymbol.value=="")
      return
 
    const response = await fetch(`http://127.0.0.1:8000/back/ohlc_chart?symbol=${currentSymbol.value}&timeframe=${currentTimeframe.value}`);
    
    const data = await response.json();
    console.log("response",data)

    if (data.length>0)
    {
      //console.log("ind_response",ind_response) 

      console.debug("loading ",currentSymbol.value,currentTimeframe.value)
      
      if (data && data.length > 0) {

        const formattedData = data.map(d => ({
          time: window.db_localTime ? window.db_localTime(d.t) : d.t,
          open: d.o, high: d.h, low: d.l, close: d.c, volume: d.bv
        }));

        //console.info("formattedData ",data)

        series.setData(formattedData);


        // Zoom finale
        /*
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
          */
          
        // chart.timeScale().scrollToPosition(0, false);
      //  nextTick( ()=>
      {
                setVolumeData(series,data.map(d => (
                {
                  time: window.db_localTime ? window.db_localTime(d.t) : d.t,
                  volume: Math.max(0,d.bv),
                  color: d.c >= d.o ? '#4bffb5aa' : '#ff4976aa'
                })));
      }
    //);
 

     
      }
      console.log("handleRefresh DONE")
    }
    else
        console.log("empty ");
  } catch (err) {
    console.debug("Errore refresh:", err.stack);
  }
};

const setSymbol = async (symbol, tf) => {
  console.log("setSymbol")
  currentSymbol.value= symbol
   currentTimeframe.value= tf
  handleRefresh();
};

// --- INIZIALIZZAZIONE ---
onMounted(  () => {  

  buildChart();
  resize()

});

onBeforeUnmount(() => {
});

onUnmounted(() => {

  if (chart) chart.remove();
});



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
/*
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
  */

  // ==============

  applyVolume(series, chart, {
      colorUp: '#26a69a',
      colorDown: '#ef5350'
  });

    let panes = chart.panes();
    //panes[0]?.setHeight(0.1);
    panes[1]?.setStretchFactor(0.5);


    //console.log("stopLoss",stopLoss );


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

      const volData = getVolume(series)  
      const timeKey = typeof data.time === 'string' ? data.time : String(data.time);
      const vol = volData.get(timeKey);

      //console.log("MOVE ",vol)

      // Update Legend
      let color = data.close >= data.open ? '#4bffb5' : '#ff4976';  
      let lbl = `<span style="color:${color}"> C: <strong>${data.close.toFixed(4)}</strong> O: <strong>${data.open.toFixed(4)}</strong> `;
      lbl += `L: <strong>${data.low.toFixed(4)}</strong> H: <strong>${data.high.toFixed(4)}</strong>`;
      lbl += ` V: <strong>${formatValue(vol)}</strong></span>`;
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
    
    if (!param || !param.point ) {
      console.log("Click cancelled");
      return;
    }
    //const candle_price = param.seriesData.get(series).close;
    const price = series.coordinateToPrice(param.point.y);
  
    if (price == null) return;

    console.log("Click at", param.time, price);  

  });

  
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

      chart.resize(width-10,height-40);

      handleRefresh();
    }
};



// ==========================

defineExpose({
  resize,
  setSymbol,
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
  border: solid 1px white;
  border-radius: 5px;
  background-color: rgba(255, 255, 255, 0.752);
  position:absolute;
  bottom:45px;
  left:1px;
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
