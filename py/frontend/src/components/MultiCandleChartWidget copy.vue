<template>
  <div class="grid-stack-item-content border rounded bg-dark text-white shadow-sm">
    <div class="header grid-stack-handle d-flex justify-content-between align-items-center p-2 bg-secondary bg-opacity-25 border-bottom">
      <div class="d-flex align-items-center">
        <span class="me-2">📈</span>
        <strong class="text-uppercase">Multi {{ currentSymbol }}</strong>

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
    </div>

   <div
      class="position-relative p-0 charts-grid"
      style="height: calc(100% - 45px); overflow: hidden;"
    >
      <div
        class="chart-legend position-absolute top-0 start-0 p-2 small chart-legend"
        v-html="legendHtml"
      ></div>

    <div class=" grid-2x2">
        <div ref="chartContainer1" class="chart-container cell">
          <div ref="mainChartRef1" class="chart-main"></div>
          <div ref="volumeChartRef1" class="chart-volume"></div>
        </div>

        <div ref="chartContainer2" class="chart-container cell">
          <div ref="mainChartRef2" class="chart-main"></div>
          <div ref="volumeChartRef2" class="chart-volume"></div>
        </div>
     
        <div ref="chartContainer3" class="chart-container cell">
          <div ref="mainChartRef3" class="chart-main"></div>
          <div ref="volumeChartRef3" class="chart-volume"></div>
        </div>

        <div ref="chartContainer4" class="chart-container cell">
          <div ref="mainChartRef4" class="chart-main"></div>
          <div ref="volumeChartRef4" class="chart-volume"></div>
        </div>
     </div>
    </div>
  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { createChart, CrosshairMode,  CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';

const props = defineProps({
  id: { type: String, required: true },
  symbol: { type: String, required: true },
  plot_config: { type: Object, default: () => ({ main_plot: {} }) }
});

const emit = defineEmits(['close', 'initialized']);

// Elementi DOM e Variabili reattive
const mainChartRef1 = ref(null);
const volumeChartRef1 = ref(null);
const mainChartRef2 = ref(null);
const volumeChartRef2 = ref(null);

const legendHtml = ref('');

const currentSymbol = ref(props.symbol);
const symbolList = ref([]);

// -------------

let _charts = []

_charts.push( { main: null, volume: null });
_charts.push( { main: null, volume: null });
_charts.push( { main: null, volume: null });
_charts.push( { main: null, volume: null });

let _series = []

_series.push( { main: null, volume: null , indicators: {} });
_series.push( { main: null, volume: null , indicators: {} });
_series.push( { main: null, volume: null , indicators: {} });
_series.push( { main: null, volume: null , indicators: {} });

let timeframes= []

timeframes.push("1m");
timeframes.push("5m");
timeframes.push("1h");
timeframes.push("1d");

/*
function getChart(timeframe){
  const idx = timeframes.indexOf(timeframe);
  return _charts[idx]
}

function getSeries(timeframe){
  const idx = timeframes.indexOf(timeframe);
  return _series[idx]
}
  */

const handleSymbols = async () => {
  handleRefresh(0);
  handleRefresh(1);
  handleRefresh(2);
  handleRefresh(3);
};
// --- LOGICA REFRESH DATI ---
const handleRefresh = async (index) => {
  try {

    let charts = _charts[index];
    let series = _series[index];
    let timeframe = timeframes[index];
    
    const responses = await fetch(`http://127.0.0.1:8000/api/symbols`);
    const datas = await responses.json();
    symbolList.value= datas["symbols"];
 
    const response = await fetch(`http://127.0.0.1:8000/api/ohlc_chart?symbol=${currentSymbol.value}&timeframe=${timeframe}`);
    const data = await response.json();

    //console.log("loading ",currentSymbol.value,currentTimeframe.value)
    
    if (data && data.length > 0) {
      // Formatta dati per Candlestick
      const formattedData = data.map(d => ({
        time: window.db_localTime ? window.db_localTime(d.t) : d.t,
        open: d.o, high: d.h, low: d.l, close: d.c
      }));

      series.main.setData(formattedData);

      // Formatta dati per Volume
      series.volume.setData(data.map(d => ({
        time: window.db_localTime ? window.db_localTime(d.t) : d.t,
        value: d.bv,
        color: d.c >= d.o ? '#4bffb5aa' : '#ff4976aa'
      })));

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

      // Zoom finale
      charts.main.timeScale().setVisibleLogicalRange({
        from: data.length - 50,
        to: data.length
      });
    }
  } catch (err) {
    console.error("Errore fetch grafico:", err);
  }
};

// --- INIZIALIZZAZIONE ---
onMounted(() => {
 // console.log("onMounted");
 
  buildChart(mainChartRef1,volumeChartRef1,0);
  buildChart(mainChartRef2,volumeChartRef2,1);
  buildChart(mainChartRef2,volumeChartRef2,2);
  buildChart(mainChartRef2,volumeChartRef2,3);

  handleRefresh(0);
  handleRefresh(1);
  handleRefresh(2);
  handleRefresh(3);
});


const resize =  (w,h) => {
    //console.log("resize ",w,h);

    
    _charts[0].main.resize(w/2,h-100);
    _charts[0].volume.resize(w/2,100);

    _charts[1].main.resize(w/2,h-100);
    _charts[1].volume.resize(w/2,100);
};


const save = ()=>
{
   //alert("save");
    return {"symbol":currentSymbol.value,"plot_config": props.plot_config}
}


const buildChart =  (mainChartRef,volumeChartRef,index) => {
 //console.log("buildChart")
  // 1. Main Chart
  let charts = _charts[index];
  let series = _series[index];

  console.log(index,charts,series)

  charts.main = createChart(mainChartRef.value, {
    layout: { background: { color: '#131722' }, textColor: '#d1d4dc' },
    grid: { vertLines: { color: '#2b2b43' }, horzLines: { color: '#2b2b43' } },
    crosshair: { mode: CrosshairMode.Normal },
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
 
  // 3. Indicatori Dinamici
  //console.log("plot_config",props.plot_config)
  if (props.plot_config.main_plot!=null)
  {
    Object.entries(props.plot_config.main_plot).forEach(([key, config]) => {
      if (config.fun === 'ema') {
        series.indicators[key] = charts.main.addSeries(LineSeries, {
          color: config.color,
          lineWidth: 1,
          lastValueVisible: false
        });
      }
    });
  }

  // 4. Sincronizzazione TimeScale
  const mainTimeScale = charts.main.timeScale();
  const volumeTimeScale = charts.volume.timeScale();

  mainTimeScale.subscribeVisibleLogicalRangeChange(range => volumeTimeScale.setVisibleLogicalRange(range));
  volumeTimeScale.subscribeVisibleLogicalRangeChange(range => mainTimeScale.setVisibleLogicalRange(range));

  // 5. Crosshair Sync e Legend
  charts.main.subscribeCrosshairMove(param => {
    if (!param.time || !param.seriesData.get(series.main)) {
      legendHtml.value = '';
      charts.volume.setCrosshairPosition(0, 0, series.volume); // Clear
      return;
    }

      
    const data = param.seriesData.get(series.main);

    //console.log("MOVE ",legendHtml)

    charts.volume.setCrosshairPosition(data.value || data.close, param.time, series.volume);

    // Update Legend
    let lbl = `C: <strong>${data.close.toFixed(3)}</strong> O: <strong>${data.open.toFixed(3)}</strong> `;
    lbl += `L: <strong>${data.low.toFixed(3)}</strong> H: <strong>${data.high.toFixed(3)}</strong>`;
    
    // Aggiungi valori indicatori alla legenda
    Object.entries(series.indicators).forEach(([key, s]) => {
      const val = param.seriesData.get(s);
      if (val) lbl += ` <span style="color:${props.plot_config.main_plot[key].color}">${key}: ${val.value.toFixed(3)}</span>`;
    });
    
    legendHtml.value = lbl;
  });

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
};

onUnmounted(() => {
  for(var i=0;i<4;i++)
  {
    if (_charts[i].main) _charts[i].main.remove();
    if (_charts[i].volume) _charts[i].volume.remove();
  }
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
  box-sizing: border-box;
  min-width: 10;
  min-height: 10;
  display: flex;
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
</style>
