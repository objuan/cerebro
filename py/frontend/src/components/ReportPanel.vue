<template>
  <div class="p-4">
    <h2 class="text-xl font-semibold mb-4">Market Report</h2>

    <div class="overflow-x-auto">
      <table class="min-w-full border rounded-xl overflow-hidden shadow-sm">
        <thead class="bg-gray-100 text-sm">
          <tr>
            <th class="px-3 py-2 text-left">Symbol</th>
            <th class="px-3 py-2 text-right">Pos</th>
            <th
              class="px-3 py-2 text-right cursor-pointer select-none"
              
              @click="setSort('gain')"
            >
              Gain %
              <span v-if="sortBy === 'gain'">
                {{ sortDir === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
            <th class="px-3 py-2 text-right">Last</th>
         
            <th class="px-3 py-2 text-right">Rel Vol 5m</th>
            <th class="px-3 py-2 text-right">Rel Vol 24h</th>
            <th class="px-3 py-2 text-right">Float</th>
            <th
              class="px-3 py-2 text-right cursor-pointer select-none"
              @click="setSort('gap')"
            >
              Gap %
              <span v-if="sortBy === 'gap'">
                {{ sortDir === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
          </tr>
        </thead>
        
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.symbol"
            class="border-t hover:bg-gray-50 text-sm"
          >
            <td class="px-3 py-2 font-medium">
              <a
                href="#"
                class="text-blue-600 hover:underline"
                @click.prevent="onSymbolClick(row.symbol)"
              >
                {{ row.symbol }}
              </a>
            </td>
            <td class="px-3 py-2 numeric">
              <span v-if="row.rank_delta > 0" class="text-green-600">
                ▲ {{ row.rank_delta }}
              </span>

              <span v-else-if="row.rank_delta < 0" class="text-red-600">
                ▼ {{ Math.abs(row.rank_delta) }}
              </span>

              <span v-else class="text-gray-400">
                –
              </span>
            </td>
            <td class="px-3 py-2 numeric"
              :style="scaleColor(row.gain, 0, 100)"
            >
              {{ row.gain.toFixed(2) }}%
            </td>
            <td class="px-3 py-2 text-right">{{ row.last }}</td>
         

            <td class="px-3 py-2 text-right">{{ row.rel_vol_5m.toFixed(2) }}</td>
            <td class="px-3 py-2 text-right">{{ row.rel_vol_24.toFixed(2) }}</td>
         
             <td class="px-3 py-2 numeric"
              :style="scaleColor(row.float, 0, 100)"
            >
              {{ formatValue(row.float) }}
            </td>
          
            <td class="px-3 py-2 numeric"
              :style="scaleColor(row.gap, 0, 100)"
            >
              {{ row.gap.toFixed(2) }}%
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
import { formatValue,scaleColor } from "@/components/js/utils";

const report = reactive({})
const sortBy = ref('gain') // 'gain' | 'gap'
const sortDir = ref('desc') // 'asc' | 'desc'

function setSort(column) {
  if (sortBy.value === column) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = column
    sortDir.value = 'desc'
  }
}

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
// =================
function onSymbolClick(symbol) {
  console.log('Symbol clicked:', symbol)

  eventBus.emit("chart-select",{"symbol" : symbol , "id": "chart_1"});

  // esempi:
  // eventBus.emit('symbol-selected', symbol)
  // openChart(symbol)
  // router.push({ name: 'symbol', params: { symbol } })
}
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
  console.log("onReportReceived",data)
  patchReport(data)
}

// =================

onMounted( async () => {
  eventBus.on("report-received", onReportReceived);

});

onBeforeUnmount(() => {
  eventBus.off("report-received", onReportReceived);
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
</style>