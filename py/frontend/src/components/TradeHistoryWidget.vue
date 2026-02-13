<template>
 
  <div class="history-anchor">

      <table class="trade-table">
        <tr>
          <td  style="width:50%;height:100%">
              <div v-if="lastTrade" style="height:100%">
                <TradeWidget :trade="lastTrade"  style="height:100%"></TradeWidget>
              </div>
          </td>
          <td>
             <button class="history-btn" @click="toggleHistory" 
              style="position: absolute;left: -38px;top:-6px">
                    📜
              </button>
          </td>
          <td  style="width:50%;height:100%">
            <table v-if="lastTrade && lastTrade.isOpen" style="width:100%;height:100%">
               <tr>
                  <td>BUY AT</td>
                  <td>{{lastSummary?.avgPrice.toFixed(2)}} $ </td>
                  <td>SELL AT</td>
                  <td>{{lastPrice}} $ </td>
                </tr>
                <tr>
                  <td>BUY</td>
                  <td>{{lastSummary?.buyTotal.toFixed(1)}} $ </td>
                  <td>SELL</td>
                  <td>{{lastSummary?.actualSell.toFixed(1)}} $ </td>
                </tr>
                <tr>
                  <td >
                    PnL
                  </td>
                  <td  >
                    <span :style="{ color: lastSummary?.pnl>0 ? 'lime' : 'red' }">
                     {{lastSummary?.pnl.toFixed(1)}} 
                    </span>
                  </td>
                   <td>
                    Gain
                  </td>
                  <td>
                    <span :style="{ color: lastSummary?.pnl>0 ? 'lime' : 'red' }">
                      {{lastSummary?.gain.toFixed(1)}} %
                    </span>
                  </td>
                </tr>
            </table>
         
          </td>
        </tr>
      </table>
      <!--TRADE LAST -->
    

      <!--  DETAIL -->

     <div v-if="showHistory" class="history-popup">
        <div>{{ props.symbol }}</div>
        <div class="history-close" @click="toggleHistory">✕</div>
        
        <TradeWidget

          v-for="(trade, ti) in tradeStore.get_trades(props.symbol)"
          :key="ti"
          class="trade-block"
          :trade = trade
        >

        </TradeWidget>
      </div>
     
  </div>
</template>

<script setup>

import { ref,onMounted,onBeforeUnmount,computed,watch  } from 'vue';
//import {send_get} from '@/components/js/utils.js'
import { eventBus } from "@/components/js/eventBus";
import { tickerStore as tickerList} from '@/components/js/tickerStore.js'
import { tradeStore } from "@/components/js/tradeStore";
import TradeWidget from '@/components/TradeWidget.vue'

const props = defineProps({
  symbol: { type: String, required: true },
});

//const tradeList = ref([]);

const showHistory = ref(false)

function toggleHistory() {
  showHistory.value = !showHistory.value
}

const lastTrade = computed(() => {
  return tradeStore.lastTrade(props.symbol);
})

const lastPrice = computed(() => {
  let ticker = tickerList.get_ticker(props.symbol);
  if (ticker)
    return ticker.last
  else
    return null;
});

const lastSummary = computed(() => {
  if (tradeStore.computeGain(lastTrade.value))
    return tradeStore.computeGain(lastTrade.value)
  else
      return null
});

/*
function tradeIsOpen(trade){
  if (!trade) return false
      return !trade.list.some(fill => fill.side === 'SELL')
}
      */

function onTradeUpdated(){
  //console.log("onTradeUpdated ",props.symbol,msg)
  /*
 if (msg.symbol === props.symbol)
  {
    // console.log("...",msg.data)
     // tradeList.value.push(msg)
      tradeStore.push(msg)
  }
      */
}

onMounted( async () => {
  eventBus.on("trade-position", onTradeUpdated);
});

onBeforeUnmount(() => {
  eventBus.off("trade-position", onTradeUpdated);
});

watch(
  () => props.symbol,
  async () => {
    /*
    tradeList.value=[]
    //tradeStore.del(props.symbol)
    let trade_list = await send_get('/trade/history',{'symbol': props.symbol})
    trade_list.forEach(  (t) =>{
      onTradeUpdated(t)
    });
*/
  } ,{ immediate: true }
      
)


</script>

<style scoped>

table td:first-child {
  text-align: left;
  padding-right: 10px;
}

table td {
  text-align: right;
}

.history-btn {
  margin-left: 50%;
  cursor: pointer;
  background: #1e293b;
  color: white;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 2px 6px;
}

.history-anchor {
  position: relative;   /* ← QUESTO è il trucco */
  display: inline-block;
  height:100%;
  margin-right: 10px;
}

.history-popup {
  position: absolute;
  top: 100%;        /* sotto al bottone */
  left: 0;          /* allineato a sinistra del bottone */
  margin-top: 6px;

  width: 420px;
  max-height: 320px;
  overflow-y: auto;

  background: #0b1220;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 10px;
  z-index: 9999;
  box-shadow: 0 10px 30px rgba(0,0,0,0.6);
  font-family: monospace;
}

.history-close {
  text-align: right;
  cursor: pointer;
  color: #aaa;
  margin-bottom: 6px;
}

.trade-table{
  width: 99%;
  height:100%;
   background: #0b1220;
  font-family: monospace;
   font-size: 13px;
}

.trade-block {

  margin-bottom: 6px;
  padding-bottom: 6px;
  padding: 6px;
   border : rgb(255, 255, 255) solid  1px
}
.clickable {
  cursor: pointer;
}


.trades-popup {
  position: absolute;
  top: 160px;
  right: 200px;
  background: #1b1b1b;
  border: 1px solid #555;
  border-radius: 8px;
  padding: 10px;
  z-index: 9999;
  min-width: 420px;
  max-height: 300px;
  overflow-y: auto;
  box-shadow: 0 6px 18px rgba(0,0,0,0.6);
}


.trade-box {
  position: relative;
  display: inline-block;
  padding: 6px;
  border: 1px solid #444;
  background: #111;
  color: white;
  cursor: pointer;
   font-family: system-ui;
  font-size: 13px;
}

.tooltip {
  position: absolute;
  top: 100%;
  left: 0;
  background: #222;
  border: 1px solid #555;
  padding: 8px;
  white-space: nowrap;
  z-index: 999;
  max-height: 300px;
  overflow-y: auto;
}

.trade-row {
 display: flex;
  align-items: center;
  gap: 12px;
  font-family: monospace; /* fondamentale per allineamento numeri */
}
.trade-col {
  min-width: 120px;
}



.trade-main {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #0f172a;
  color: #e2e8f0;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid #334155;
  cursor: help;
}


</style>