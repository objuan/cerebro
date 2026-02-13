<template>
 
  <div>
      <p>
       DAY PNL  <strong>{{ tradeStore.day_PNL.toFixed(2) }} $</strong> 
        (# {{ tradeStore.total }} )
      </p>
      <p>WIN/LOSS <strong>{{ tradeStore.win  }}/{{ tradeStore.loss  }}</strong></p>
     <div >
        
        <TradeWidget

          v-for="(trade, ti) in tradeStore.get_all_trades()"
          :key="ti"
          class="trade-block"
          :trade = trade
          :full_mode="true"
        >

        </TradeWidget>
      </div>
     
  </div>
</template>

<script setup>

import { onMounted,onBeforeUnmount  } from 'vue';
import {send_get} from '@/components/js/utils.js'
import { eventBus } from "@/components/js/eventBus";
import { tradeStore } from "@/components/js/tradeStore";
import TradeWidget from '@/components/TradeWidget.vue'



function onTradeUpdated(msg){
 tradeStore.push(msg)
}

onMounted( async () => {
  eventBus.on("trade-position", onTradeUpdated);

   let trade_list = await send_get('/trade/history/day')
    trade_list.forEach(  (t) =>{
      onTradeUpdated(t)
    });
});

onBeforeUnmount(() => {
  eventBus.off("trade-position", onTradeUpdated);
});

</script>

<style scoped>


</style>