<template>
        <div v-if="index" >
          <table style="width: 100%;height:100%; border: 1px solid;">
            <tr>
               <td v-for="col in cols" :key="col" >
                 
                 <table style="width: 100%;height:100%;">
                    <td style="min-width:40px"><strong>{{col_name[col]}}</strong></td>
                     <td 
                        v-for="(row, i) in index [col]" 
                          :key="row.symbol"
                          :style="{ backgroundColor: assignColor(i), width:row.percent }"
                        >
                         <a href="#" class="text-blue-600 hover:underline" @click.prevent="onSymbolClick(row.symbol)">
                             {{ formatSymbol(row.symbol) }} 
                            </a>
                          <br>{{ formatValue(row.value) }}
                       
                      </td>
                 
                  </table>
                  
               </td>
            </tr>
          </table>
           
        </div>
  
</template>

<script setup>

import {onMounted, onUnmounted,ref} from 'vue';
import {formatSymbol,formatValue} from "@/components/js/utils";
import { eventBus } from "@/components/js/eventBus";
//import { tickerStore  } from "@/components/js/tickerStore";
let tickerMap = {}
const MAX = 10
const cols = ['pct_1m','pct_5m','pct_10m']


const col_map = 
{
  'pct_1m': 'vol_1m',
  'pct_5m': 'vol_5m',
  'pct_10m': 'vol_10m',
}
const col_name = 
{
  'pct_1m': '1 M',
  'pct_5m': '5 M',
  'pct_10m': '10 M',
}
  
//const cols_value = ['vol_1m','vol_5m','vol_10m']



const index = ref(null)

const colors = [
  
  
  "#ffe119", // giallo
  "#f58231", // arancione
  "#46f0f0", // ciano
  "#bcf60c", // lime
  "#fabebe",  // rosa chiaro
  "#3cb44b", // verde
  "#911eb4", // viola
  
  "#4363d8", // blu
  "#f032e6", // magenta
  
  
  "#e6194b", // rosso
]


function onSymbolClick(symbol) {
  console.log('Symbol clicked:', symbol)
  eventBus.emit("chart-select",{"symbol" : symbol , "id": "chart_1"});
}


function assignColor(i)
{
    return colors[i]
}

function buildIndexes(matrix) {
  const makeIndex = (key) =>
    matrix
      .map(r => ({
        symbol: r.symbol,
        percent: r[key] || 0,   // numero puro
        value : r[col_map[key]].toFixed(0) || 0
      }))
      .sort((a, b) => b.percent - a.percent)
      .slice(0, 10)           // 🔥 prendi solo i primi 10
      .map(r => ({
        symbol: r.symbol,
        value: r.value,
        percent: r.percent.toFixed(2) + '%'  // format DOPO
      }))

  return {
    pct_1m: makeIndex('pct_1m'),
    pct_5m: makeIndex('pct_5m'),
    pct_10m: makeIndex('pct_10m')
  }
}

function rebuild() {
   const data = []

  for (const symbol in tickerMap) {
    const arr = tickerMap[symbol]

    if (!arr || arr.length === 0) continue

    // ultimi N elementi
    const last1 = arr.slice(-1)
    const last5 = arr.slice(-5)
    const last10 = arr.slice(-10)

    // funzione somma
    const sum = (list) =>
      list.reduce((acc, m) => acc + (m.v * m.c || 0), 0)

    const row = {
      symbol: symbol,
      vol_1m: sum(last1),
      vol_5m: sum(last5),
      vol_10m: sum(last10),
      pct_1m: 0,
      pct_5m: 0,
      pct_10m: 0
    }

    // 2. Totali globali
    const total_1m = data.reduce((a, r) => a + r.vol_1m, 0)
    const total_5m = data.reduce((a, r) => a + r.vol_5m, 0)
    const total_10m = data.reduce((a, r) => a + r.vol_10m, 0)

    // 3. Percentuali
    data.forEach(r => {
      r.pct_1m = total_1m ? (r.vol_1m / total_1m) * 100 : 0
      r.pct_5m = total_5m ? (r.vol_5m / total_5m) * 100 : 0
      r.pct_10m = total_10m ? (r.vol_10m / total_10m) * 100 : 0
    })

    data.push(row)
  }

  //console.log("matrix:", data)
  index.value = buildIndexes(data)
}

function on_candle(msg){
  if (msg.m =="full" && msg.tf =="1m")
  {
  //  console.log(msg)
      const s = msg.s

       if (!tickerMap[s]) {
      tickerMap[s] = []
    }

    const arr = tickerMap[s]

    if (arr.length < MAX) {
      arr.push(msg)
    } else {
      arr.splice(0, 1) // oppure indice circolare se vuoi top performance
      arr.push(msg)
    }

     // console.log("→", s, tickerMap[s].length)


      rebuild()
  }
}


/*
function onTickerReceived(ticker) {

  console.log(" → ticker:", ticker);

}
  */

onMounted( async () => {
    //eventBus.on("ticker-received", onTickerReceived);
})
onUnmounted( async () => {
   // eventBus.off("ticker-received", onTickerReceived);
})
defineExpose({
  
  on_candle

});


</script>

<style scoped>

</style>