<template>
  <div ref="container" class="grid-stack-item-content border rounded bg-dark text-white shadow-sm" >
    <div v-if="!props.multi_mode" class="header grid-stack-handle d-flex justify-content-between align-items-center p-2 bg-secondary bg-opacity-25 border-bottom">
      <div class="d-flex align-items-center"  >
        <span class="me-2">📈</span>
        <strong class="text-uppercase">Single {{ currentSymbol }}</strong>

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
          <option value="1m">1m</option>
          <option value="5m">5m</option>
          <option value="1h">1h</option>
          <option value="1d">1d</option>
        </select>
        <button @click="$emit('close', id)" class="btn btn-sm btn-outline-light border-0 close-btn">✕</button>
      </div>
    </div>
   <div v-if="props.multi_mode" class="bulk_header" >
        {{ currentTimeframe }}
    </div>
    <div class="position-relative flex-grow-1 p-0" style="height: calc(100%-45px ); overflow: hidden;">
      <div class="chart-legend position-absolute top-0 start-10 p-2 z-4 small" v-html="legendHtml"></div>
      
      <div ref="chartContainer" class="chart-container h-100 w-100 d-flex flex-column">
        <div ref="mainChartRef" class="flex-grow-1 w-100"></div>
        <div ref="volumeChartRef" style="height: 100px;" class="w-100 border-top border-secondary"></div>
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { createChart, CrosshairMode,  CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';

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
const currentTimeframe = ref(props.timeframe);
const currentSymbol = ref(props.symbol);
const symbolList = ref([]);
const container = ref(null)

// Oggetti Chart e Series (non reattivi per performance)
let charts = { main: null, volume: null };
let series = { main: null, volume: null, indicators: {} };

let timeframe_start = {}
timeframe_start["1m"] = 50
timeframe_start["5m"] = 50
timeframe_start["1h"] = 24
timeframe_start["1d"] = 30


const handleSymbols = async () => {
  handleRefresh();
};
const setSymbol = async (symbol) => {
  currentSymbol.value= symbol
  handleRefresh();
};


// --- LOGICA REFRESH DATI ---
const handleRefresh = async () => {
  try {
    const responses = await fetch(`http://127.0.0.1:8000/api/symbols`);
    const datas = await responses.json();
    //console.log("symbols",datas)
    symbolList.value= datas["symbols"];
 
    const response = await fetch(`http://127.0.0.1:8000/api/ohlc_chart?symbol=${currentSymbol.value}&timeframe=${currentTimeframe.value}`);
    const data = await response.json();

    console.log("loading ",currentSymbol.value,currentTimeframe.value)
    
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
        from: data.length - timeframe_start[currentTimeframe.value],
        to: data.length
      });
    }
  } catch (err) {
    console.error("Errore fetch grafico:", err);
  }
};


// --- INIZIALIZZAZIONE ---
onMounted(() => {
 // const { width, height } = container.value.getBoundingClientRect()

 // console.log("onMounted ",width-10,height-10);
  buildChart();
  handleRefresh();

  resize()
});

const fullResize =  () => {
    //console.log("c full resize ",w,h);

    //charts.main.resize(w,h-100);
    //charts.volume.resize(w,100);
};

const resize =  () => {
    const { width, height } = container.value.getBoundingClientRect()

    console.log("c resize ",width,height,container);
   // console.log(charts.main)

    charts.main.resize(width-10,height-100);
    charts.volume.resize(width-10,94);

    handleRefresh();
};



const buildChart =  () => {
 //console.log("buildChart")
  // 1. Main Chart
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
  if (charts.main) charts.main.remove();
  if (charts.volume) charts.volume.remove();
});

defineExpose({
  resize,
  fullResize,
  setSymbol
});

</script>

<style scoped>
.chart-legend {
  left:  20px;
  pointer-events: none;
  background: rgba(19, 23, 34, 0.7);
  border-bottom-right-radius: 4px;
  z-index: 10 !important;
}
.timeframe-selector {
  width: auto;
  padding: 0 0.5rem;
}
.bulk_header{
  position:absolute;
  z-index: 20 !important;
}

</style>
