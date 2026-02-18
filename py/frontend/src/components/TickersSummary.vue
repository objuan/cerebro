<template>
<div style="width: 100%">
  <div class="sort-bar">
    <span></span>

    <button
      :class="{ active: sortBy === 'gain' }"
      @click="sortBy = 'gain'"
    >
      Gain
    </button>

    <button
      :class="{ active: sortBy === 'gap' }"
      @click="sortBy = 'gap'"
    >
      Gap
    </button>
 <button
      :class="{ active: sortBy === 'day_volume' }"
      @click="sortBy = 'day_volume'"
    >
      V
    </button>
     <button
      :class="{ active: sortBy === 'rel_vol_5m' }"
      @click="sortBy = 'rel_vol_5m'"
    >
      Vol5
    </button>
     <button
      :class="{ active: sortBy === 'rel_vol_24' }"
      @click="sortBy = 'rel_vol_24'"
    >
      VolD
    </button>
  </div>

  <header class="py-1 mb-1 border-bottom bg-light">
 
     <div class="d-flex flex-wrap gap-1 items-container">

      <div
        v-for="item in sortedTickers"
        :key="item.symbol"
        class="card ticket-card"
      >
        <div class="card-body p-0 d-flex justify-content-between align-items-center">
          
            <table style="width: 100%; height: 100%;">
              <tr style="height : 60%">
                <td>
                   <div class="fw-bold">
                        <a href="#" class="text-blue-600 hover:underline" @click.prevent="onSymbolClick(item.symbol)">
                              {{ item.symbol }} 
                            </a>

                    </div>
                </td>
                <td>
                  <div
                      class="fw-bold ms-1"
                      :class="item.gain >= 0 ? 'text-success' : 'text-danger'"
                    >
                      {{ Number(item.gain).toFixed(1) }}%
                    </div>
                </td>
              </tr>
            <tr style="height : 40%">
              <td class="volume">
                  {{ formatValue(item.report?.day_volume) }}
              </td>
              <td class="volume" :style="{ color: item.report?.rel_vol_5m>0 ? 'green' : 'red' }">
                  {{item.report?.rel_vol_5m.toFixed(1)}}%
              </td>
            </tr>
        

     
          </table>
           <!-- STARS-->
          <div class="star-wrapper" v-if="item.summary">
            <div class="star-grid">
              <div
                v-for="key in orderedKeys"
                :key="key"
                class="cell"
                :title="getRank(key)"
              >
              <span v-if="isTrue(item.summary[key])">
                  <svg
                    v-if="key === 'news'"
                    class="icon "
                    :style="{color:newsColor(item.summary.news-1)}"
                    viewBox="0 0 24 24"
                  >
                    <path
                      d="M13.5 2s.5 3-2 6-3 4-3 6a5 5 0 0 0 10 0c0-3-2-5-3-6s-2-3-2-6z"
                      fill="currentColor"
                    />
                  </svg>

                  <svg
                    v-else
                    class="icon "
                    :style="{color:priceColor(item.summary[key]) }"
                    viewBox="0 0 24 24"
                  >
                    <path
                      d="M12 2l3 7 7 .5-5.5 4.5 2 7L12 17l-6.5 4 2-7L2 9.5 9 9z"
                      fill="currentColor"
                    />
                  </svg>
                </span>
              </div>
            </div>
             
            <div class="report" v-if="item.report">
              <div class="title">{{ item.symbol }}</div>
                <div class="row">
                    <div class="label">From Last</div>
                    <div class="value">{{ secondsFrom(item.ts)  }}</div>
              </div>
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
                  :style="{ color: priceColor(item.summary.rel_vol_24) }"
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

               <div class="row" v-if="item.summary.news>0" :style="{color:newsColor(item.summary.news-1)}">
                <div class="label">Last New</div>
                <div class="value">
                    {{ item.summary.news-1 }} Day(s)
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
                  @click.prevent="getSymbolInfos(item.symbol)">
                   Get Company Info
                </a>
              </li>

               <li>
                <a class="dropdown-item"
                  href="#"
                  @click.prevent="getNews(item.symbol)">
                   Get News
                </a>
              </li>
              <li><hr class="dropdown-divider"></li>
              <li>
                <a class="dropdown-item"
                  href="#"
                   @click.prevent="updateNews(item.symbol)">
                   Update  News
                </a>
              </li>
               <li><hr class="dropdown-divider"></li>
                <li>
                <a class="dropdown-item"
                  href="#"
                  @click.prevent="addToDayWatch(item.symbol)">
                   Add to day watch list
                </a>
              </li>
              <li><hr class="dropdown-divider"></li>
              <li>
                <a class="dropdown-item"
                  href="#"
                  @click.prevent="addToDayBlack(item.symbol)">
                   Add to day black list
                </a>
              </li>
             
              <li>
                <a class="dropdown-item text-danger"
                  href="#"
                  @click.prevent="addToEverBlack(item.symbol)">
                  Add to permanet black list
                </a>
              </li>
            </ul>
          </div>

        </div>
      </div>

    </div>
    <NewsWidget
        v-if="showNews"
        :symbol="selectedSymbol"
        @close="showNews = false"
      />
  </header>
</div>
</template>

<script setup>

import {  ref, computed, onMounted, onUnmounted ,onBeforeUnmount } from 'vue';
//import { computed } from 'vue';
//import { liveStore } from '@/components/liveStore.js'; // Assicurati che il percorso sia corretto
import { send_get,formatValue,priceColor,newsColor } from '@/components/js/utils.js'; // Usa il percorso corretto
import { eventBus } from "@/components/js/eventBus";
import { tickerStore as tickerList } from "@/components/js/tickerStore";
import { reportStore as report } from "@/components/js/reportStore";
import NewsWidget from "@/components/NewsWidget.vue";

const showNews = ref(false)
const selectedSymbol= ref(null)
const sortBy = ref('gain'); // 'gain' | 'gap'
const now = ref(Date.now())
let timer = null

const orderedKeys = [
  'float', 'gain', 'gap',
  'news', 'price', 'volume'
]

const sortedTickers = computed(() => {
  const list = tickerList.get_sorted();

  return [...list].sort((a, b) => {
    const av = a.report?.[sortBy.value] ?? 0;
    const bv = b.report?.[sortBy.value] ?? 0;
    return bv - av; // decrescente
  });
});

const isTrue = (v) => v > 0

defineProps({
})


function getRank(key){
  if (key =="news")
    return "news";
  else
    return key;
}
function getSymbolInfos(symbol){
  console.log("getSymbolInfos", symbol)
  const url = `https://finance.yahoo.com/quote/${encodeURIComponent(symbol)}`;
    window.open(url, "_blank");
}

async function updateNews(symbol){
    await send_get("/api/news/update", {"symbol": symbol})
}
function getNews(symbol){
  console.log("selectedSymbol", symbol)
  selectedSymbol.value = symbol;
  showNews.value = true;
}

function addToDayWatch(symbol) {
  //console.log("Add to watchlist:", symbol);
   send_get("/api/admin/add_to_watch", {"name": "day_watch", "type":"day", "symbol": symbol})
}

function addToDayBlack(symbol) {
  //console.log("Add to watchlist:", symbol);
   send_get("/api/admin/add_to_black", {"mode":"day", "symbol": symbol})
}

function addToEverBlack(symbol) {
  send_get("/api/admin/add_to_black", {"mode":"all", "symbol": symbol})
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

function secondsFrom(ts) {
  if (!ts) return ''

  // se ts è in secondi unix → moltiplica per 1000
  const timestamp = ts < 1e12 ? ts * 1000 : ts

  const diff = Math.floor((now.value - timestamp) / 1000)

  if (diff < 60) return `${diff}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  return `${Math.floor(diff / 3600)}h`
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

  timer = setInterval(() => {
    now.value = Date.now()
  }, 1000)

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
    clearInterval(timer)
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
.volume{
  top: 0px;
 font-family: monospace; 
 font-size: 13px;
}
.items-container {
   height: calc(100vh - 90px); 
  overflow-y: auto;
  overflow-x: hidden;   /* ❌ niente scroll orizzontale */
  width: 100%;
  margin-right: 2px;

  
  display: flex;
  flex-direction: column;
  justify-content: flex-start;  /* 🔥 allinea in alto */
  align-items: stretch;         /* opzionale */
}
.items-container::-webkit-scrollbar {
  width: 6px;              /* sottile */
}

.items-container::-webkit-scrollbar-track {
  background: #111;
}

.items-container::-webkit-scrollbar-thumb {
  background: #555;
  border-radius: 4px;
}

.items-container::-webkit-scrollbar-thumb:hover {
  background: #888;
}
.items-container {
  scrollbar-width: thin;
  scrollbar-color: #555 #111;
}

.sort-bar{
  display:flex;
  align-items:center;
  gap:2px;
  padding:2px 2px;
  font-size:13px;
  background:#222;
  color:white;
  border-bottom:2px solid #333;
}

.sort-bar button{
  border:1px solid #555;
  background:#111;
  color:#ccc;
  padding:3px 2px;
  border-radius:4px;
  cursor:pointer;
}

.sort-bar button.active{
  background:#00e676;
  color:#000;
  font-weight:700;
}

.icon {
  width: 18px;
  height: 18px;
}
.star {
  color: rgb(255, 217, 0);
}

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
 width: 100%;
  max-height:50px
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
  left: -35px;
  transform: translateX(-50%);
  z-index: 100;
  
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