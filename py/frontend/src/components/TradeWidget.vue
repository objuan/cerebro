<template>
        <div  class="trade-block" >
          <div class="trade-header">
            <span v-if="props.full_mode">
              <strong>{{ props.trade.symbol }} </strong>
            </span>
            <span v-if="tradeIsOpen(props.trade)"  style="color:orange">
              Open
            </span>
            <span v-else
              :style="{ color: trade.pnl >= 0 ? 'lime' : 'red' }"
            >
              PnL: {{ props.trade.pnl.toFixed(2) }}
              (G:{{ props.trade.balance.toFixed(2) }},
              C:{{-props.trade.comm.toFixed(1) }})
            </span>
          </div>

          <div
            v-for="(fill, fi) in props.trade.list"
            :key="fi"
            class="trade-row"
          >
            <span :style="{ color: fill.side === 'BUY' ? 'lime' : 'red' }">
              {{ fill.side }}
            </span>
            {{ formatTime(fill.time*1000) }}           
            @{{ fill.price.toFixed(3) }}x{{ fill.size }}
            ({{ fill.comm.toFixed(1) }})
          </div>
        </div>
  
</template>

<script setup>

import {} from 'vue';
import {formatTime} from '@/components/js/utils.js'

const props = defineProps({
  trade: {  required: true },
  full_mode: { type: Boolean, default: false } 
});

//const trade = ref(props.trade);

function tradeIsOpen(){
      return !props.trade.list.some(fill => fill.side === 'SELL')
}

/*
watch(
  () => props.trade,
  (newTrade) => {
    console.log('trade changed', newTrade)
    // fai quello che ti serve qui
  },
  { immediate: true, deep: true }
)
*/
</script>

<style scoped>

.history-btn {
  margin-left: 10px;
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

.trade-block {
  border-bottom: 1px solid #334155;
  margin-bottom: 6px;
  padding-bottom: 6px;
}
.clickable {
  cursor: pointer;
}

.trade-block{
   padding: 6px;
   border : white solid
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
  font-size: 12px;
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