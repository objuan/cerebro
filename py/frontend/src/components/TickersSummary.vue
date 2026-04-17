<template>
<div style="width: 100%">
  <div class="sort-bar">
    <span>
    {{count_sum}}</span>
     <button @click="toggleShowAll()">
      .
    </button>


    <button style="flex-grow: 1;" class="btn btn-sm btn-dark" @click="menuOpen = !menuOpen">
             {{sortBy}} ⚙️
    </button>
    
    <div v-if="menuOpen" class="filter-popup">
        <table>
          <tr>
            <td>
                <button
                  :class="{ active: sortBy === 'gain' }"
                  @click="sortBy = 'gain';menuOpen=false"
                >
                  Gain
                </button>

                <button
                  :class="{ active: sortBy === 'gap' }"
                  @click="sortBy = 'gap';menuOpen=false"
                >
                  Gap
                </button>
                <button
                  :class="{ active: sortBy === 'day_volume' }"
                  @click="sortBy = 'day_volume';menuOpen=false"
                >
                  V
                </button>
                <button
                  :class="{ active: sortBy === 'rel_vol_5m' }"
                  @click="sortBy = 'rel_vol_5m';menuOpen=false"
                >
                  Vol5
                </button>
                <button
                  :class="{ active: sortBy === 'rel_vol_24' }"
                  @click="sortBy = 'rel_vol_24';menuOpen=false"
                >
                  VolD
                </button>
            </td>
          </tr>
          <tr>
            <td>
               <button
                  :class="{ active: sortBy === 'volume_diff' }"
                  @click="sortBy = 'volume_diff';menuOpen=false"
                >
                  Last Volume
                </button>

                 <button
                  :class="{ active: sortBy === 'volume_diff_quote' }"
                  @click="sortBy = 'volume_diff_quote';menuOpen=false"
                >
                  Last Volume Quote
                </button>
            </td>
          </tr>
          <tr>
            <td>
                <button
                  :class="{ active: sortBy === 'trend_perc' }"
                  @click="sortBy = 'trend_perc';menuOpen=false"
                >
                  Trend %
                </button>
                 <button
                  :class="{ active: sortBy === 'trend_perc_all' }"
                  @click="sortBy = 'trend_perc_all';menuOpen=false"
                >
                  Trend All %
                </button>
                <button
                  :class="{ active: sortBy === 'trend_len' }"
                  @click="sortBy = 'trend_len';menuOpen=false"
                >
                  Trend #
                </button>
            </td>
          </tr>
          <tr>
            <td>
              <div style="display:flex; flex-direction:column; gap:4px;">
                
                <label style="font-size:11px;">
                  Min Volume: {{formatValue(minVolume) }}
                </label>

                <input
                  type="range"
                  min="0"
                  max="1000000"
                  step="50000"
                  v-model="minVolume"
                  @input="updateTickers"
                />

              </div>
            </td>
          </tr>

        </table>
       
      </div>
  </div>

  <header class="py-1 mb-1 border-bottom bg-light">
 
     <div class="items-container">

      <div
        v-for="item in sortedTickers"
        :key="item.symbol"
        class="card ticket-card"
      >
        <div class="card-body p-0 d-flex justify-content-between align-items-center">
            <div class="time-bar">
            <div class="time-bar-fill" :style="{ width: progress(item) + '%' }"></div>
          </div>
            <table style="width: 100%; height: 100%;" class="mini-table">
              <tr style="height : 40%">
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
            <tr style="height : 30%">
              <td class="volume">
                <span :style="{ color: rankColor(item.summary?.day_volume,{ r: 0, g: 0, b: 0 },{ r: 0,  g: 170, b: 90 }) }">
                    {{ formatValue(item.report?.day_volume) }}
                </span>
                  
              </td>
              <td class="volume" :style="{ color: item.report?.rel_vol_5m>0 ? 'green' : 'red' }">
                  {{item.report?.rel_vol_5m.toFixed(1)}}%
              </td>
            </tr>
            
           <tr style="height : 30%" v-if="!hasTradeOpen(item.symbol)">
              <td class="volume" >
                  {{formatValue(item.strategy.get(item.symbol,"1m","TRADE")?.volume_diff)}}
              </td>
              <td class="volume" >
                   {{ ( formatValue( item.strategy.get(item.symbol,"1m","TRADE")?.volume_diff * item.last))}}$
              </td>
            </tr>
            <tr v-else>
              <td  style="color: #F00;" class="volume" colspan="2" v-if="lastTrade(item.symbol).isOpen" >{{formatValue(item.strategy.get(item.symbol,"1m","TRADE")?.volume_diff)}} OPEN {{ tradeStore.currentGain(lastTrade(item.symbol)).toFixed(1) }}% </td>
              <td   style="color:black" class="volume" colspan="2" v-else >Close {{ tradeStore.currentGain(lastTrade(item.symbol)).toFixed(1) }}%</td>
            </tr>

          </table>
           <!-- STARS-->
          <div class="star-wrapper" v-if="item.summary">
            <div class="star-grid">
              <div
                v-for="key in orderedKeys"
                :key="key"
                class="cell"
                :title="key"
              >
              <span >

                  <svg
                    v-if="key === 'news' "
                    class="icon "
                    :style="{color:newsColor(item.summary.news)}"
                    viewBox="0 0 24 24"
                  >
                    <path
                      d="M13.5 2s.5 3-2 6-3 4-3 6a5 5 0 0 0 10 0c0-3-2-5-3-6s-2-3-2-6z"
                      fill="currentColor"
                    />
                  </svg>

                  <svg
                    v-else-if="key == 'last' "
                    class="icon "
                    :style="{color:rankColor(item.summary[key]) }"
                    viewBox="0 0 24 24"
                  >
                      <path
                        d="M12 2C7 2 3 4.2 3 7v10c0 2.8 4 5 9 5s9-2.2 9-5V7c0-2.8-4-5-9-5zm0 2c4.4 0 7 1.6 7 3s-2.6 3-7 3-7-1.6-7-3 2.6-3 7-3zm0 14c-4.4 0-7-1.6-7-3V9c1.7 1.2 4.4 2 7 2s5.3-.8 7-2v6c0 1.4-2.6 3-7 3z"
                        fill="currentColor"
                      />
                  </svg>

                  <svg
                    v-else
                    class="icon "
                    :style="{color:rankColor(item.summary[key]) }"
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

            <!-- TOOLTIP -->
            <div class="report" v-if="item.report">
              <div class="title">{{ item.symbol }}</div>
              
                <div class="row">
                <div class="label">scan</div>
                <div class="value" style="font-size: 10px;">{{ item.report.scan }} </div>
              </div>

               <div class="row">
                <div class="label">last</div>
                <div class="value">{{ item.last }} </div>
              </div>

              <div class="row">
                    <div class="label">From Last</div>
                    <div class="value">{{ item.secs_from }} secs</div>
              </div>
              <div class="row">
                <div class="label">Rank</div>
                <div class="value">{{ item.report.rank }}</div>
              </div>

              <div class="row">
                <div class="label">Volume</div>
                <div class="value"
                :style="{ color: rankColor(item.summary.day_volume) }"
                >{{ formatValue(item.report.day_volume) }}   ({{ item.summary.day_volume.rank }})</div>
              </div>

              <div class="row">
                <div class="label">Price</div>
                <div
                  class="value"
                  :style="{ color: rankColor(item.summary.last) }"
                >
                  {{ item.report.last }} ({{ item.summary.last.rank }})
                </div>
              </div>

              <div class="row">
                <div class="label">From Close</div>
                <div
                  class="value"
                  :style="{ color: rankColor(item.summary.gain) }"
                >
                  {{ item.report.gain.toFixed(1) }}% ({{ item.summary.gain.rank }})
                </div>
              </div>

              <div class="row">
                <div class="label">Gap</div>
                <div
                  class="value"
                  :style="{ color: rankColor(item.summary.gap) }"
                >
                  {{ item.report.gap.toFixed(1) }}% ({{ item.summary.gap.rank }})
                </div>
              </div>

              <div class="row">
                <div class="label">Float</div>
                <div
                  class="value"
                  :style="{ color: rankColor(item.summary.float) }"
                >
                  {{ formatValue(item.report.float) }} ({{ item.summary.float.rank }})
                </div>
              </div>

              <div class="row">
                <div class="label">Rel 24</div>
                <div
                  class="value"
                  :style="{ color: rankColor(item.summary.rel_vol_24) }"
                > 
                  {{ item.report.rel_vol_24.toFixed(1) }}%  ({{ item.summary.rel_vol_24.rank }})
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
              <li>
                <a class="dropdown-item"
                  href="#"
                   @click.prevent="updateNewsAll()">
                   Update  News All
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

               <li>
                <a class="dropdown-item"
                  href="#"
                  @click.prevent="clearDayWatch(item.symbol)">
                   Clear day watch list
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

import {  ref, computed, onMounted, onUnmounted ,onBeforeUnmount ,watch} from 'vue';
//import { computed } from 'vue';
//import { liveStore } from '@/components/liveStore.js'; // Assicurati che il percorso sia corretto
import { send_get,formatValue,newsColor,rankColor } from '@/components/js/utils.js'; // Usa il percorso corretto
import { eventBus } from "@/components/js/eventBus";
import { tickerStore as tickerList } from "@/components/js/tickerStore";
import { reportStore as report } from "@/components/js/reportStore";
import NewsWidget from "@/components/NewsWidget.vue";
import { staticStore } from '@/components/js/staticStore.js';
import { tradeStore } from "@/components/js/tradeStore";

const showNews = ref(false)
const selectedSymbol= ref(null)
const sortBy = ref('gain'); // 'gain' | 'gap'
const now = ref(Date.now())
const showAll = ref(false)
const sortedTickers = ref([])
const menuOpen = ref(false)
const minVolume = ref(500000)
let timer = null

const orderedKeys = [
  'float', 'gain', 'gap',
  'news', 'last', 'rel_vol_24'
]

const progress = (item) => {
  if (!item.secs_from) return 0;
  if ( item.secs_from< 10) return 100;
  const f =  Math.min(10, item.secs_from-10)/10
  return 100 - f * 100;
}
/*
function hasTrade(symbol){
  return tradeStore.lastTrade(symbol)!=null
}
  */
function hasTradeOpen(symbol){
  const last = lastTrade(symbol)
  return last!=null && last.isOpen
}
function lastTrade(symbol){
  return tradeStore.lastTrade(symbol)
}

//const sortedTickers = computed(() => {
function updateTickers()
{
  const list = tickerList.get_sorted();

  //console.log("tickerList",list.length)
 //  console.log(sortBy.value )
  if (showAll.value)
  {
    sortedTickers.value= [...list].sort((a, b) => {
      const aMissing = !a.secs_from;
      const bMissing = !b.secs_from;

      if (aMissing !== bMissing) return aMissing - bMissing;
      
      return (b.report?.[sortBy.value] ?? 0) - (a.report?.[sortBy.value] ?? 0);
    });
  }
  else
  {
    sortedTickers.value= [...list]
       .filter(t => 
          t.secs_from &&
          (t.report?.day_volume ?? 0) >= minVolume.value
        )  // tiene solo quelli con secs_from
      .sort((a, b) => {
        /*
        if (sortBy.value == "trend_perc")
          return  b.strategy.get(b.symbol,"1m","TRADE")?.trend_perc - 
                  a.strategy.get(a.symbol,"1m","TRADE")?.trend_perc;
        else  if (sortBy.value == "trend_perc_all")
          return  b.strategy.get(b.symbol,"1m","TRADE")?.trend_perc_all - 
                  a.strategy.get(a.symbol,"1m","TRADE")?.trend_perc_all;
        else  if (sortBy.value == "trend_len")
          return  b.strategy.get(b.symbol,"1m","TRADE")?.trend_len - 
                  a.strategy.get(a.symbol,"1m","TRADE")?.trend_len;
        else
        */
         if (sortBy.value == "volume_diff")
            return  b.strategy.get(b.symbol,"1m","TRADE")?.volume_diff - 
                  a.strategy.get(a.symbol,"1m","TRADE")?.volume_diff;
        else  if (sortBy.value == "volume_diff_quote")
          return  b.strategy.get(b.symbol,"1m","TRADE")?.volume_diff_quote - 
                  a.strategy.get(a.symbol,"1m","TRADE")?.volume_diff_quote;
        else
          return (b.report?.[sortBy.value] ?? 0) - (a.report?.[sortBy.value] ?? 0);
      });
    }
      
//});
  }

const count_sum = computed(() => {
  return tickerList.get_list().length
});

function toggleShowAll(){
  showAll.value = !showAll.value
  updateTickers()
}
/*
const sortedTickers = computed(() => {
  const list = tickerList.get_sorted();

  return [...list].sort((a, b) => {
    const aMissing = !a.secs_from;
    const bMissing = !b.secs_from;

    if (aMissing !== bMissing) return aMissing - bMissing;

    return (b.report?.[sortBy.value] ?? 0) - (a.report?.[sortBy.value] ?? 0);
  });
});
*/
/*
const isTrue = (v) =>
{
  console.log(v.name)
  return v.value>0
}
  */

defineProps({
})

/*
function getRank(key){
  if (key =="news")
    return "news";
  else
    return key;
}
    */
function getSymbolInfos(symbol){
  console.log("getSymbolInfos", symbol)
  const url = `https://finance.yahoo.com/quote/${encodeURIComponent(symbol)}`;
    window.open(url, "_blank");
}

async function updateNews(symbol){
    await send_get("/api/news/update", {"symbol": symbol})
}
async function updateNewsAll(){
    await send_get("/api/news/update/all")
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
function clearDayWatch(symbol) {
  //console.log("Add to watchlist:", symbol);
   send_get("/api/admin/clear_day_watch", {"name": "day_watch", "type":"day", "symbol": symbol})
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
  updateTickers()
  //console.log("Summary → ticker:", ticker);
  //updateSymbol(ticker);
}

function secondsFrom(ts) {
  if (!ts) return ''

  // se ts è in secondi unix → moltiplica per 1000
  const timestamp = ts < 1e12 ? ts * 1000 : ts

  const diff = Math.floor((now.value - timestamp) / 1000)

  return diff
}

function onReportReceived(data){
  //console.log("onReportReceived",data)
   for (const [symbol, ] of Object.entries(data)) {
     //console.log(symbol,rep)
      //tickerList.value[symbol].summary = report.get_sum_rank(symbol)
      //console.log( "..",symbol)
      tickerList.push({"symbol": symbol, "summary" : report.get_sum_rank(symbol)})
      tickerList.push({"symbol": symbol, "report" : report.get_report(symbol)})
   }
   updateTickers()

}

async function onStart(){
  console.log("onStart")
  minVolume.value = staticStore.get('summary.filter.min_volume',400000);
console.log("onStart",minVolume.value)
}

onMounted( async () => {
  eventBus.on("ticker-received", onTickerReceived);
  eventBus.on("report-received", onReportReceived);
  eventBus.on("on-start", onStart)

  
  timer = setInterval(() => {
    now.value = Date.now()
    try{
      const list = tickerList.get_list();
      list.forEach( ( item)=>
      {
        tickerList.push({"symbol": item.symbol,"secs_from": secondsFrom(item.ts)})
      });
    }catch(e){
      console.error(e)
    }
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
    eventBus.off("on-start", onStart)
    clearInterval(timer)
});

onUnmounted(() => {


});

watch(minVolume, (newVal, ) => {
  
  staticStore.set('summary.filter.min_volume',newVal)
  //saveProp("event.filter",v)
}, { deep: true })

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

.time-bar{
  position:absolute;
  left:0;
  bottom:0;
  width:100%;
  height:2px;
  background:#333;
}

.time-bar-fill{
  height:100%;
  width:0%;
  background:#00ff88;
  transition:width .2s linear;
}

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
  min-height:60px;
   max-height:60px
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
.mini-table {
  width: 100%;
  height: 100%;
  border-collapse: collapse;
}

.mini-table td {
  padding: 0px 2px;
  line-height: 1;
  vertical-align: middle;
}
.mini-table tr {
  height: 18px;
}


.filter-popup-wrapper {
  position: relative;
  display: inline-block;
}

.filter-popup {
  position: absolute;
  top: 80px;
  right: 100;
  background: #1b1b1b;
  border: 1px solid #444;
  padding: 8px 10px;
  border-radius: 6px;
  z-index: 1000;
  min-width: 140px;

  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}
.filter-bar{
  display:flex;
  align-items:center;
  gap:12px;
  padding:1px;
  background:#111;
  color:white;
  font-size:13px;
  border-bottom:2px solid #333;
}

.filter-item{
  display:flex;
  align-items:center;
  gap:6px;
  cursor:pointer;
}
</style>