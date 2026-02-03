<template>
  <div>
    <div class="chart-header ">
      {{title}}
    </div>
    <div ref="chartContainer" class="chart"></div>
   </div>
</template>

<script setup>

import { ref,onMounted,onUnmounted,watch,onBeforeUnmount } from "vue";
import { createChart ,LineSeries  } from '@/components/js/ind.js';

const colors = ["#2962FF", "#D50000", "#2E7D32", "#FF6D00", "#6A1B9A"];

const props = defineProps({
  title: String
});

const chartContainer = ref(null);
let chart = null;
let resizeObserver;
let seriesMap={}

function update_data(data) {
  console.log("update_data", data);

  const incomingSymbols = new Set(Object.keys(data));

  // 🧹 1) RIMUOVI serie che non esistono più
  Object.keys(seriesMap).forEach(symbol => {
    if (!incomingSymbols.has(symbol)) {
      chart.removeSeries(seriesMap[symbol]);
      delete seriesMap[symbol];
      console.log("removed series", symbol);
    }
  });

  // 🎨 contatore colori stabile
  let i = 0;

  // ➕ 2) CREA o AGGIORNA
  Object.entries(data).forEach(([symbol, points]) => {

    const formatted = points.map(p => ({
      time: p.timestamp / 1000,
      value: p.value,
    }));
 console.log("formatted", formatted)
    // se NON esiste → crea
    if (!seriesMap[symbol]) {
      const series = chart.addSeries(LineSeries, {
        title: symbol,
        lineWidth: 1,
        color: colors[i++ % colors.length],
      });

      series.setData(formatted);
      seriesMap[symbol] = series;

      console.log("created series", symbol);
    }
    // se esiste → aggiorna
    else {
      seriesMap[symbol].setData(formatted);
      console.log("updated series", symbol);
    }
  });

  chart.timeScale().fitContent();
}

onMounted(() => {
    chart = createChart(chartContainer.value, {
        width: chartContainer.value.clientWidth,
        //height: 600,
         timeScale: {
          timeVisible: true,      // mostra HH:mm:ss
          secondsVisible: true,   // fondamentale per timeframe 10s
          rightBarStaysOnScroll: true,
        },

        localization: {
          timeFormatter: (time) => {
            const d = new Date(time * 1000);
            return d.toLocaleTimeString(); // HH:mm:ss nella barra X
          },
        },
    });

    //series = chart.addSeries(CandlestickSeries);
    //series.setData(props.data);

  //update_data();

  // 🔥 OSSERVA IL RESIZE DEL CONTAINER
  resizeObserver = new ResizeObserver(() => {
      const { width, height } =
        chartContainer.value.getBoundingClientRect();

        chart.resize(width , height );
         chart.timeScale().fitContent();
  });
  resizeObserver.observe(chartContainer.value);

});

watch(() => props.data, (newData) => {
    console.log("newData",newData)
    //update_data(newData)
 
});

onUnmounted(() => {
    if (chart) {
        chart.remove();
    }
});

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect();
});

defineExpose({
  update_data,
});


</script>

<style scoped>

.chart {
  width: 100%;
  height: 200px;
}

.chart-header {
  display: flex;
  flex-direction: row;
  gap: 1px;
  width: 100%;
  height: 30px;
  background-color: #cdcdff;
}

</style>