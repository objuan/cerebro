<template>
  <header class="py-1 mb-1 border-bottom bg-light">
 
     <div class="d-flex flex-wrap gap-2">

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
            <small class="text-muted"> {{ Number(item.last).toFixed(1) }}</small>
          

          <div
            class="fw-bold ms-3"
            :class="item.gain >= 0 ? 'text-success' : 'text-danger'"
          >
            {{ Number(item.gain).toFixed(1) }}%
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

import {  onMounted, onUnmounted ,onBeforeUnmount } from 'vue';
//import { computed } from 'vue';
//import { liveStore } from '@/components/liveStore.js'; // Assicurati che il percorso sia corretto
import { send_get } from '@/components/js/utils.js'; // Usa il percorso corretto
import { eventBus } from "@/components/js/eventBus";
import { tickerStore as tickerList } from "@/components/js/tickerStore";

//const symbolList = ref([]);

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

defineProps({
})

onMounted( async () => {
  eventBus.on("ticker-received", onTickerReceived);

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
.ticket-card {
  min-width: 160px;
  max-width: 250px;
}
</style>