<template>
  <header class="py-1 mb-1 border-bottom bg-light">
 
     <div class="d-flex flex-wrap gap-1">

      <div
        v-for="item in tickerList.get_list()"
        :key="item.symbol"
        class="card ticket-card"
      >
        <div class="card-body p-2 d-flex justify-content-between align-items-center">
          
         
            <div class="fw-bold">
                <a href="#" class="text-blue-600 hover:underline" @click.prevent="onSymbolClick(item.symbol)">
                      {{ item.symbol }}
                    </a>
            </div>

          <div
            class="fw-bold ms-1"
            :class="item.gain >= 0 ? 'text-success' : 'text-danger'"
          >
            {{ Number(item.gain).toFixed(1) }}%
          </div>
          
           <!-- STARS-->
          <div class="star-wrapper">
            <div class="star-grid">
              <div
                v-for="key in orderedKeys"
                :key="key"
                class="cell"
                :title="key"
              >
                <span v-if="isTrue(item.summary[key])">⭐</span>
              </div>
            </div>
             
            <div class="report">
              <div class="title">{{ item.symbol }}</div>

              <div class="row">
                <div class="label">Rank</div>
                <div class="value">{{ item.report.rank }}</div>
              </div>

              <div class="row">
                <div class="label">Volume</div>
                <div class="value">{{ formatValue(item.report.day_volume) }}</div>
              </div>

              <div class="row">
                <div class="label">Price</div>
                <div
                  class="value"
                  :style="{ color: priceColor(item.summary.price) }"
                >
                  {{ item.report.last }}
                </div>
              </div>

              <div class="row">
                <div class="label">From Close</div>
                <div
                  class="value"
                  :style="{ color: priceColor(item.summary.gain) }"
                >
                  {{ item.report.gain.toFixed(1) }}%
                </div>
              </div>

              <div class="row">
                <div class="label">Gap</div>
                <div
                  class="value"
                  :style="{ color: priceColor(item.summary.gap) }"
                >
                  {{ item.report.gap.toFixed(1) }}%
                </div>
              </div>

              <div class="row">
                <div class="label">Float</div>
                <div
                  class="value"
                  :style="{ color: priceColor(item.summary.float) }"
                >
                  {{ formatValue(item.report.float) }}
                </div>
              </div>

              <div class="row">
                <div class="label">Rel 24</div>
                <div
                  class="value"
                  :style="{ color: priceColor(item.summary.float) }"
                >
                  {{ item.report.rel_vol_24.toFixed(1) }}%
                </div>
              </div>

              <div class="row">
                <div class="label">Rel 5</div>
                <div class="value">
                  {{ item.report.rel_vol_5m.toFixed(1) }}%
                </div>
              </div>
            </div>

          </div>

           <!-- Bottone menu contestuale -->
          <div class="dropdown">
            <button
              class="btn btn-sm btn-light border-0"
              type="button"
              data-bs-toggle="dropdown"
              aria-expanded="false"
              @click.stop
            >
              ⋮
            </button>

            <ul class="dropdown-menu dropdown-menu-end">
              <li>
                <a class="dropdown-item"
                  href="#"
                  @click.prevent="openChart(item.symbol)">
                  Open
                </a>
              </li>
              <li>
                <a class="dropdown-item"
                  href="#"
                  @click.prevent="addToWatchlist(item.symbol)">
                  Add to Watchlist
                </a>
              </li>
              <li><hr class="dropdown-divider"></li>
              <li>
                <a class="dropdown-item text-danger"
                  href="#"
                  @click.prevent="addToBlack(item.symbol)">
                  Add to black list
                </a>
              </li>
            </ul>
          </div>

        </div>
      </div>

    </div>
  </header>
</template>

<script setup>

import {   onMounted, onUnmounted ,onBeforeUnmount } from 'vue';
//import { computed } from 'vue';
//import { liveStore } from '@/components/liveStore.js'; // Assicurati che il percorso sia corretto
import { send_get,formatValue } from '@/components/js/utils.js'; // Usa il percorso corretto
import { eventBus } from "@/components/js/eventBus";
import { tickerStore as tickerList } from "@/components/js/tickerStore";
import { reportStore as report } from "@/components/js/reportStore";

//const symbol_summary = ref({})

const orderedKeys = [
  'float', 'gain', 'gap',
  'news', 'price', 'volume'
]

const isTrue = (v) => v > 0

defineProps({
})

//const symbolList = ref([]);
const priceColor = (v) => {
  // clamp sicurezza
  v = Math.max(0, Math.min(1, Number(v) || 0))

  // bianco → verde acceso
  const start = { r: 255, g: 255, b: 255 }   // bianco
  const end   = { r: 0,   g: 230, b: 118 }   // #00e676

  const r = Math.round(start.r + (end.r - start.r) * v)
  const g = Math.round(start.g + (end.g - start.g) * v)
  const b = Math.round(start.b + (end.b - start.b) * v)

  return `rgb(${r}, ${g}, ${b})`
}

function openChart(symbol) {
  eventBus.emit("chart-select", { symbol, id: "chart_1" });
}

function addToWatchlist(symbol) {
  console.log("Add to watchlist:", symbol);
  eventBus.emit("watchlist-add", { symbol });
}

function addToBlack(symbol) {
  send_get("/api/admin/add_to_black", {"symbol": symbol})
}

// Esponiamo i dati dello store al template
//const liveData = computed(() => liveStore.state.dataByPath);
function onSymbolClick(symbol) {
  console.log('Symbol clicked:', symbol)
  eventBus.emit("chart-select",{"symbol" : symbol , "id": "chart_1"});
}

function onTickerReceived() {
  //console.log("Summary → ticker:", ticker);
  //updateSymbol(ticker);
}

function onReportReceived(data){
  //console.log("onReportReceived",data)
   for (const [symbol, ] of Object.entries(data)) {
     //console.log(symbol,rep)
      //tickerList.value[symbol].summary = report.get_sum_rank(symbol)
      //console.log( "..",tickerList.value[symbol])
      tickerList.push({"symbol": symbol, "summary" : report.get_sum_rank(symbol)})
      tickerList.push({"symbol": symbol, "report" : report.get_report(symbol)})
   }

}


onMounted( async () => {
  eventBus.on("ticker-received", onTickerReceived);
 eventBus.on("report-received", onReportReceived);
  /*
  let data = await send_get("/api/symbols")
  //console.log("Symbols ",data.symbols)
  symbolList.value =[]
  data.symbols.forEach(symbol => {
    symbolList.value.push({"symbol" : symbol});
  });
 */
});

onBeforeUnmount(() => {
  eventBus.off("ticker-received", onTickerReceived);
   eventBus.off("report-received", onReportReceived);
});

onUnmounted(() => {


});

/*
function updateSymbol(ticket){
    //console.log("updateSymbol", ticket);
    const item = symbolList.value.find(
      s => s.symbol === ticket.symbol
    );
    if (item) {
      item.last = ticket.last;
      item.gain = ticket.gain.toFixed(2);
    }
}
    */

defineExpose({
 // updateSymbol,
});


</script>

<style scoped>

.star-grid {
  display: grid;
  grid-template-columns: repeat(3, 12px);
  grid-template-rows: repeat(2, 12px);
  gap: 2px;
}

.cell {
  width: 12px;
  height: 12px;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ticket-card {
  min-width: 160px;
  max-width: 250px;
}
.star-wrapper {
  position: relative;
  display: inline-block;
}

/* Tooltip nascosto di default */
.report {
  position: absolute;
  /* bottom: 120%;          sopra la grid */
  top: 120%;              /* 👈 sotto la grid */
  left: 100%;
  transform: translateX(-50%);
  
  background: #111;
  color: #eee;
  font-size: 11px;
  padding: 8px 10px;
  border-radius: 6px;
  white-space: nowrap;

  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, transform 0.15s ease;
  
  z-index: 999;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}

/* freccina */
.report::after {
  content: "";
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border-width: 6px;
  border-style: solid;
  border-color: #111 transparent transparent transparent;
}

/* compare al passaggio del mouse */
.star-wrapper:hover .report {
  opacity: 1;
  transform: translateX(-50%) translateY(-4px);
}
.report-item{
  text-align: start
  
}
.report-item.green {
  color: #00e676; /* verde trader style */
  font-weight: 600;
}

.report {
  display: grid;
  grid-template-columns: auto auto;
  column-gap: 14px;
  row-gap: 4px;

  background: #111;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 11px;
  color: #ddd;
  white-space: nowrap;
}

.title {
  grid-column: 1 / -1;
  font-weight: 700;
  margin-bottom: 6px;
  text-align: center;
  color: #fff;
}

.row {
  display: contents; /* magia: fa comportare label/value come celle grid */
}

.label {
  opacity: 0.7;
  text-align: left;     /* 👈 labels allineate a sinistra */
  justify-self: start;  /* 👈 forza la cella a sinistra nella grid */
}

.value {
  text-align: right;
  justify-self: end;    /* valori ben allineati a destra */
}
</style>