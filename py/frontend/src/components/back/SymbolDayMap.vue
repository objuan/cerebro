<template>
  <div class="table-wrapper">

    <!-- 🔥 BOTTONI HEADER -->
    <div class="actions">
      <button @click="selectAll">Tutti</button>
      <button @click="selectNone">Nessuno</button>
      <button @click="selectTimeRange(10, 15,1)">
         10AM-15PM(1)
      </button>
       <button @click="selectTimeRange(10, 15,3)">
         10AM-15PM(3)
      </button>
    </div>

    <table>
      <thead>
        <tr>
          <th>Select</th>
          <th>Symbol</th>
          <th v-for="h in hours" :key="h">
            {{ h }}:00
          </th>
        </tr>
      </thead>

      <tbody>
        <tr 
          v-for="item in symbols" 
          :key="item.symbol"
          :class="{ active: selectedSymbols.includes(item.symbol) }"
        >
          <td>
            <input 
              type="checkbox"
              :value="item.symbol"
              v-model="selectedSymbols"
            />
          </td>

          <td class="symbol">{{ item.symbol }}</td>

          <td 
            v-for="h in hours" 
            :key="h"
            class="cell"
          >
            <span v-if="hasDataInHour(item, h)">X</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="selected">
      Selezionati: {{ selectedSymbols }}
    </div>
  </div>
</template>


<script setup>
import { ref } from 'vue'

const symbols = ref(null)

// lista dinamica dei selezionati
const selectedSymbols = ref([])
/*
// 🔥 dati di esempio (usa i tuoi reali)
const symbols = [
  { symbol: "YMT", min_timestamp: 1770991980000, max_timestamp: 1771000380000 },
  { symbol: "XXII", min_timestamp: 1770987780000, max_timestamp: 1770993420000 }
]
  */

// ore 0 → 23
const hours = Array.from({ length: 24 }, (_, i) => i)

// funzione controllo
function hasDataInHour(item, hour) {
  const date = new Date(item.min_timestamp)

  const hourStart = new Date(date)
  hourStart.setHours(hour, 0, 0, 0)

  const hourEnd = new Date(date)
  hourEnd.setHours(hour, 59, 59, 999)

  return (
    hourStart.getTime() <= item.max_timestamp &&
    hourEnd.getTime() >= item.min_timestamp
  )
}


// 🔥 Seleziona tutti
function selectAll() {
  selectedSymbols.value = symbols.value.map(s => s.symbol)
}

// ❌ Deseleziona tutti
function selectNone() {
  selectedSymbols.value = []
}

// 🕙 Seleziona chi ha dati nel range ore
function selectTimeRange(startHour, endHour, minCount = 1) {
  selectedSymbols.value = symbols.value
    .filter(item => {
      let count = 0

      for (let h = startHour; h <= endHour; h++) {
        if (hasDataInHour(item, h)) {
          count++
        }

        // 🔥 ottimizzazione: esci prima se raggiunto minCount
        if (count >= minCount) {
          return true
        }
      }

      return false
    })
    .map(item => item.symbol)
}
function setup(list){
  symbols.value = list
}


defineExpose({
  setup,
  selectedSymbols
});


</script>

<style scoped>
.table-wrapper {
  overflow-x: auto;
}

table {
  border-collapse: collapse;
  font-size: 12px;
}

th, td {
  border: 1px solid #ddd;
  padding: 4px 6px;
  text-align: center;
}

.symbol {
  font-weight: bold;
  position: sticky;
  left: 0;
  background: white;
}

.cell {
  width: 30px;
}

.cell span {
  color: green;
  font-weight: bold;
}

.selected {
  margin-top: 10px;
  font-size: 13px;
}
.active {
  background-color: #f0f8ff;
}
</style>
