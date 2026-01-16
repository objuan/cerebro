<template>
 
  <div class="card-body p-1">
    <div v-if="isCurrent" class="d-flex align-items-center gap-3 w-100">
      
      <div class="d-flex align-items-center gap-1">
        TRADE <strong>{{ tradeData.timeframe }}</strong>
     
      </div>

      <div class="d-flex align-items-center gap-1">
        Quantity
        <select
          v-model="quantity"
          class="form-select form-select-sm"
          style="width: 80px"
        >
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="300">300</option>
        </select>
      </div>
      <div class="d-flex align-items-center gap-1">
        Cost <strong>{{ Number(tradeData.total_price_usd).toFixed(1) }}</strong>
        ({{ Number(tradeData.price).toFixed(1) }}x{{ tradeData.quantity }})
      </div>
       <div class="d-flex align-items-center gap-1">
        Loss <strong>{{ Number(tradeData.loss_usd).toFixed(1) }}</strong>
      </div>
      <div class="d-flex align-items-center gap-1">
        Gain <strong>{{ Number(tradeData.profit_usd).toFixed(1) }}</strong>
      </div>
        
      <div class="d-flex align-items-center gap-1">
        Position <strong>{{ symbol }} {{position}}</strong>
      </div>
      
    </div>
    <div class="d-flex align-items-center gap-1">
      <button class="btn btn-sm btn-success"
            @click="send_limit_order()"
          >FAST BUY</button>

      <button class="btn btn-sm btn-success"
            @click="send_buy_at_level()"
          >BUY LIMIT</button>

          
      <button class="btn btn-sm btn-success"
            @click="send_order_bracket()"
          >SEND MARKER</button>


      <button class="btn btn-sm btn-danger"
            @click="clear_all()"
          >SELL ALL</button>
     </div>
  </div>
</template>

<script setup>


import { ref,watch,computed,onMounted,onBeforeUnmount  } from 'vue';
import { liveStore } from '@/components/js/liveStore.js'; // Assicurati che il percorso sia corretto
import {send_post,send_mulo_get} from '@/components/js/utils.js'
import { eventBus } from "@/components/js/eventBus";
import {order_limit,clear_all_orders,order_buy_at_level,order_bracket} from "@/components/js/orderManager";

const props = defineProps({
  symbol: { type: String, required: true },
});

const liveData = computed(() => liveStore.state.dataByPath);
const isCurrent = computed(() => {
  return tradeData.value && tradeData.value.symbol == props.symbol;
});
const tradeData = ref(null);
const quantity = ref(null);
const ticker = ref(null);
const position = ref(null);

function send_limit_order(){
  order_limit(props.symbol,quantity.value,ticker.value.last )
}

function send_buy_at_level(){
  order_buy_at_level(props.symbol,quantity.value,ticker.value.last )
}
function send_order_bracket(){
  order_bracket(props.symbol,tradeData.value.timeframe,quantity.value,ticker.value.last )
}

function clear_all(){
  clear_all_orders(props.symbol);
}

function onTaskOrderReceived(order){
  if (order.symbol == props.symbol)
  {
    //console.log("TradeConsole → task ordine:", order);
  }
}

function onOrderReceived(order) {
  if (order.symbol == props.symbol)
  {
    //console.debug("TradeConsole → ordine:", order);
  }
}
function onTickerReceived(_ticker) {
  if (_ticker.symbol == props.symbol)
  {
   // console.log("TradeConsole → ticker:", _ticker);
    ticker.value =_ticker
  }
}

function onPositionUpdated(msg){
   if (msg.symbol == props.symbol)
   {
      position.value = msg.position
  }
}

onMounted( async () => {
  eventBus.on("task-order-received", onTaskOrderReceived);
  eventBus.on("order-received", onOrderReceived);
  eventBus.on("ticker-received", onTickerReceived);
  eventBus.on("update-portfolio", onPositionUpdated);
  eventBus.on("update-position", onPositionUpdated);

   
  let pos_list = await send_mulo_get('/account/positions')
  pos_list.forEach(  (val) =>{
        val["type"] = "POSITION"
        onPositionUpdated(val);
  });
});

onBeforeUnmount(() => {
  eventBus.off("task-order-received", onTaskOrderReceived);
  eventBus.off("order-received", onOrderReceived);
  eventBus.off("ticker-received", onTickerReceived);
  eventBus.off("update-portfolio", onPositionUpdated);
  eventBus.off("update-position", onPositionUpdated);
});


// sync STORE → SELECT

watch(
  () =>
  {
    return liveData.value['trade.tradeData.'+props.symbol];
  } ,
  v => {
    if (v != null) tradeData.value = v;
  },
  { immediate: true }
);

watch(
  () => tradeData.value?.quantity,
  v => {
    if (v != null) quantity.value = v;
  },
  { immediate: true }
);

/* =========================
   INPUTS → STORE + SAVE
   ========================= */

watch(quantity,  async (newValue, oldValue) => {
  if (oldValue && oldValue!= newValue)
  {
     console.log("quantity",newValue, oldValue)
     tradeData.value.quantity = newValue
     let ret = await send_post("/api/trade/marker/update",
     {
          symbol: props.symbol,
          timeframe: tradeData.value.timeframe,
          data: tradeData.value,
     });
     if (ret.status === "ok") {
          tradeData.value = ret.data
          console.log("Trade marker set qny", tradeData.value);

          liveStore.updatePathData('trade.tradeData.'+props.symbol, tradeData.value);
      }
    }
});


</script>