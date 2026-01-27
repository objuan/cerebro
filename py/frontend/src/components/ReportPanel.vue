<template>
  <div class="p-0">
    
    <div class="overflow-x-auto">
      <table class="min-w-full border rounded-xl overflow-hidden shadow-sm">
        <thead class="bg-gray-100 text-sm">
          
          <th 
            v-for="col in columns" 
            :key="col.bind"
            class="px-3 py-2 text-left font-semibold text-gray-700 uppercase tracking-wider"
             @click="setSort(col.bind)"
          >
            {{ col.title }}

              <span v-if="sortBy === col.bind">
                {{ sortDir === 'asc' ? '▲' : '▼' }}
              </span>
          </th>
        </thead>
        
        <tbody v-if="props.mode=='report'">
            <tr
              v-for="row in rows"
              :key="row.symbol"
              class="border-t hover:bg-gray-50 text-sm"
            >
                <td v-for="col in columns" :key="col.bind" class="px-0 py-0">
    
                  <template v-if="col.type === 'chart_link'">
                    <a href="#" class="text-blue-600 hover:underline" @click.prevent="onSymbolClick(row[col.bind])">
                      {{ row[col.bind] }}
                    </a>
                  </template>

                  <template v-else-if="col.type === 'rank'">
                    <span v-if="row[col.bind] > 0" class="text-green-600">▲ {{ row[col.bind] }}</span>
                    <span v-else-if="row[col.bind] < 0" class="text-red-600">▼ {{ Math.abs(row[col.bind]) }}</span>
                    <span v-else class="text-gray-400">–</span>
                  </template>

                  <template v-else>
                    <span class ="cell" :style="formatStyle(row[col.bind] ,columnsMap[col.bind] )">
                      {{ formatField(row[col.bind], col) }}
                    </span>
                  </template>

                </td>

            </tr>
        </tbody>

         <tbody v-if="props.mode!=='report'">
            <tr
              v-for="(row, index) in events"
              :key="row.symbol || index"
              class="border-t hover:bg-gray-50 text-sm"
            >
                <td v-for="col in columns" :key="col.bind" class="px-0 py-0">
    
                  <template v-if="col.type === 'chart_link'">
                    <a href="#" class="text-blue-600 hover:underline" @click.prevent="onSymbolClick(row[col.bind])">
                      {{ row[col.bind] }}
                    </a>
                  </template>

                  <template v-else-if="col.type === 'rank'">
                    <span v-if="row[col.bind] > 0" class="text-green-600">▲ {{ row[col.bind] }}</span>
                    <span v-else-if="row[col.bind] < 0" class="text-red-600">▼ {{ Math.abs(row[col.bind]) }}</span>
                    <span v-else class="text-gray-400">–</span>
                  </template>

                  <template v-else-if="col.type === 'str'">
                       {{ row[col.bind] }}
                  </template>

                   <template v-else-if="col.type === 'time'">
                       {{ formatUnixTimeOnly(row[col.bind]) }}
                  </template>

                  <template v-else>
                    <span class ="cell" :style="formatStyle(row[col.bind] ,columnsMap[col.bind] )">
                      {{ formatField(row[col.bind], col) }}
                    </span>
                  </template>

                </td>

            </tr>
        </tbody>

      </table>
    </div>
  </div>
</template>

<script setup>
import { computed,onMounted,onBeforeUnmount,reactive,ref  } from 'vue'
import { eventBus } from "@/components/js/eventBus";
import { formatValue,interpolateColor ,formatUnixTimeOnly} from "@/components/js/utils";// scaleColor

const  props = defineProps({
  mode: {
    type: String,
    default: 'report'
  }
})

const report = reactive({})
const events = reactive([])
const sortBy = ref('gain') // 'gain' | 'gap'
const sortDir = ref('desc') // 'asc' | 'desc'

const rows = computed(() => {
  const key = sortBy.value
  const dir = sortDir.value === 'asc' ? 1 : -1

  return Object.entries(report)
    .map(([symbol, data]) => ({
      symbol,
      ...data
    }))
    .sort((a, b) => {
      const av = a[key] ?? -Infinity
      const bv = b[key] ?? -Infinity
      return (av - bv) * dir
    })
})
const columns = computed(() => {
   if (props.mode=="report")
      return columnsData;
    else
      return evt_columnsData;
});

const columnsMap = computed(() => {
   if (props.mode=="report")
      return columnsDataMap;
    else
      return ev_columnsDataMap;
});

const columnsData = [
   {"title": "Change From Close" ,"bind" : "gain" , "type" :"perc", "decimals": 2,"sort":"true", "colors":{ "range_min": 0 , "range_max":10 ,  "color_min": "#FFFFFF" , "color_max":"#14A014"   } },
   {"title": "Symbol/News" ,"bind" : "symbol",  "type" :"chart_link" },
   {"title": "Pos" ,"bind" : "rank_delta",  "type" :"rank" },
   {"title": "Price","decimals": 2 ,"bind" : "last"},
   {"title": "Volume","bind" : "day_volume", "type" :"volume" },
   {"title": "Float" ,"bind" : "float","type" :"volume" },
   {"title": "Rel Vol 1d","bind" : "rel_vol_24", "decimals": 2 },
   {"title": "Rel Vol 5m","bind" : "rel_vol_5m", "decimals": 2 },
   {"title": "Gap","bind" : "gap", "type" :"perc" , "decimals": 1,"sort":"true", "colors":{ "range_min": 0 , "range_max":10 ,   "color_min": "#FFFFFF" , "color_max":"#14A014"    } }
]

const evt_columnsData = [
   {"title": "Time" ,"bind" : "ts",  "type" :"time" },
   {"title": "Symbol/News" ,"bind" : "symbol",  "type" :"chart_link" },
   {"title": "Price","decimals": 2 ,"bind" : "last"},
   {"title": "Volume","bind" : "day_volume", "type" :"volume" },
   {"title": "Float" ,"bind" : "float","type" :"volume" },
   {"title": "Rel Vol 1d","bind" : "rel_vol_24", "decimals": 2 },
   {"title": "Rel Vol 5m","bind" : "rel_vol_5m", "decimals": 2 },
   {"title": "Gap","bind" : "gap", "type" :"perc" , "decimals": 1,"sort":"true", "colors":{ "range_min": 0 , "range_max":10 ,   "color_min": "#FFFFFF" , "color_max":"#14A014"    } },
   {"title": "Change From Close" ,"bind" : "gain" , "type" :"perc", "decimals": 2,"sort":"true", "colors":{ "range_min": 0 , "range_max":10 ,  "color_min": "#FFFFFF" , "color_max":"#14A014"   } },
   {"title": "Strategy" ,"bind" : "name",  "type" :"str" }
]

const columnsDataMap = columnsData.reduce((acc, col) => {
  acc[col.bind] = col;
  return acc;
}, {});

const ev_columnsDataMap = columnsData.reduce((acc, col) => {
  acc[col.bind] = col;
  return acc;
}, {});

console.log("columnsDataMap",columnsDataMap)

function smart_fixed(value,decimals){
  if (value)
    return value.toFixed(decimals)
  else
  return 0;
}

function formatField(value, colData){
  //console.log("formatField", value, colData)
  let type = colData["type"]
  if (!type) type ="float"
  let decimals = colData["decimals"]
  if (!decimals) decimals=0
  

  //console.log("type ", type,"decimals",decimals )
  if (type =="volume"){
     return  formatValue(value) 
  }
  if (type =="float"){
     return smart_fixed(value,decimals) 
  }
  if (type =="perc"){
     return smart_fixed(value,decimals) +"%"
  }
  if (type =="rank"){
     if (value >0) return "▲ "+value
     else if (value <0) return "▼ "+value
     else return "-"
  }
  if (type =="chart_link"){
      return `<a
                href="#"
                class="text-blue-600 hover:underline"
                @click.prevent="onSymbolClick(row.symbol)"
              >
                ${value}
              </a>`
  }
  if (type =="str"){
     return value;
  }
  return value
}
function formatStyle(value, colData)
{
  //console.log("formatStyle", value, colData)

  let colors = colData["colors"]
  if (colors)
  {
    //"range_min": -2 , "range_max":10 ,  "color_min": "#FFFFFF" , "color_max":"#14A014"   
    let range_min = colors["range_min"]
    let range_max = colors["range_max"]
    let color_min = colors["color_min"]
    let color_max = colors["color_max"]

    const clamped = Math.min(Math.max(value, range_min), range_max)
    const t = (clamped - range_min) / (range_max - range_min || 1)
    let s =   interpolateColor(color_min,color_max,t,0.5)

    return {
      backgroundColor:s
    }
  }
  else
    return ""
}

function setSort(column) {
  if (sortBy.value === column) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = column
    sortDir.value = 'desc'
  }
}


// =================

function onSymbolClick(symbol) {
  console.log('Symbol clicked:', symbol)

  eventBus.emit("chart-select",{"symbol" : symbol , "id": "chart_1"});

  // esempi:
  // eventBus.emit('symbol-selected', symbol)
  // openChart(symbol)
  // router.push({ name: 'symbol', params: { symbol } })
}
console.log("onSymbolClick",onSymbolClick)
// =================

function patchReport(incoming) {
  for (const [symbol, data] of Object.entries(incoming)) {
    if (!report[symbol]) {
      report[symbol] = {}
    }

    Object.assign(report[symbol], data)
  }
}

function onReportReceived(data){
  //console.log("onReportReceived",data)
  patchReport(data)
}

function onEventReceived(data){
  //console.log("onEventReceived",data)
 // events.push(data)
 // 1. Aggiunge il nuovo evento in cima alla lista (indice 0)
  events.unshift(data);
  
  // 2. Se la lista supera i 100 elementi, rimuove l'ultimo (il più vecchio)
  if (events.length > 100) {
    events.pop(); 
    // In alternativa puoi usare: events.splice(100); 
    // che rimuove tutto ciò che va oltre l'indice 99
  }
  
}


// =================

onMounted( async () => {
  if (props.mode=="report")
      eventBus.on("report-received", onReportReceived);
  else
      eventBus.on("event-received", onEventReceived);

});

onBeforeUnmount(() => {
  if (props.mode=="report")
      eventBus.off("report-received", onReportReceived);
  else
      eventBus.off("event-received", onEventReceived);
});

</script>


<style scoped>
.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
th {
  transition: color 0.15s;
}
th:hover {
  color: #2563eb; /* blue-600 */
}
.cell{
  width:100%;
  height: 100%;
  display: block;
}
</style>