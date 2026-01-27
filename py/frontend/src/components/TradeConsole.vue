<template>
 
  <div class="card-body p-1">
    <div class="d-flex align-items-center gap-3 w-100">
      
      <div  v-if="isCurrent" class="d-flex align-items-center gap-1">
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
          <option :value="500">500</option>
          <option :value="1000">1000</option>
        </select>
      </div>

      <div  v-if="isCurrent" class="d-flex align-items-center gap-1">
        Cost <strong>{{ Number(tradeData.total_price_usd).toFixed(1) }}</strong>
        ({{ Number(tradeData.price).toFixed(1) }}x{{ tradeData.quantity }})
      </div>
       <div  v-if="isCurrent" class="d-flex align-items-center gap-1">
        Loss <strong>{{ Number(tradeData.loss_usd).toFixed(1) }}</strong>
      </div>
      <div  v-if="isCurrent" class="d-flex align-items-center gap-1">
        Gain <strong>{{ Number(tradeData.profit_usd).toFixed(1) }}</strong>
      </div>
        
     <div class="ms-auto d-flex align-items-center gap-2">
       
      <!-- -->
      <div v-if="lastTrade" class="position-badge">
        <b style="color:red">{{ lastTrade.symbol }}</b>

        <span>
          BUY: {{ formatTime(lastTrade.entry_time) }}
          {{ lastTrade.entry_size }}@{{ lastTrade.entry_price }}
        </span>

        <!-- Mostrati SOLO se non null -->
        <span v-if="lastTrade.exit_time != null">
          → SELL: {{ formatTime(lastTrade.exit_time) }}
          @ {{ lastTrade.exit_price }}
        </span>

        <span 
          v-if="lastTrade.pnl != null"
          :style="{ color: lastTrade.pnl >= 0 ? 'lime' : 'red' }"
        >
          PnL: {{ lastTrade.pnl.toFixed(2) }}
        </span>
      </div>

      <div class="position-badge position-main clickable"   @click="toggleTrades">
        {{symbol}} {{ position }}
      </div>

      <!-- ALL TOOLTIP  -->
      <div v-if="showAll" class="trades-popup">
        <div 
          v-for="(t, i) in tradeList.slice().reverse()" 
          :key="i"
          class="trade-row"
        >
          BUY {{ formatTime(t.entry_time) }} @ {{ t.entry_price }}

          <template v-if="t.exit_time != null">
            → SELL: {{ formatTime(t.exit_time) }} @ {{ t.exit_price }}
          </template>

          <span 
            v-if="t.pnl != null"
            :style="{ color: t.pnl >= 0 ? 'lime' : 'red' }"
          >
            | PnL: {{ t.pnl.toFixed(2) }}
          </span>
        </div>
      </div>

      
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

      <div class="card p-2 d-flex justify-content-between align-items-center">
        <div class="w-100" style="color:black" v-html="active_order_task"></div>
      </div>

      <div class="card p-2 d-flex justify-content-between align-items-center ms-auto">
        <div class="w-100" style="color:black" v-html="active_order"></div>
      </div>
     
    </div>

     
  </div>
</template>

<script setup>


import { ref,watch,computed,onMounted,onBeforeUnmount  } from 'vue';
import { liveStore } from '@/components/js/liveStore.js'; // Assicurati che il percorso sia corretto
import {send_post,send_get} from '@/components/js/utils.js'
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
const quantity = ref(100);
const ticker = ref(null);
const position = ref(null);

const tradeList = ref([]);
const showAll = ref(false)

const active_order = ref("...");
const active_order_task = ref("...");

const lastTrade = computed(() => {
  if (tradeList.value.length === 0) return null
  return tradeList.value[tradeList.value.length - 1]
})

function toggleTrades() {
  showAll.value = !showAll.value
}

function formatTime(ms) {
  return new Date(ms).toLocaleTimeString('it-IT', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}
function send_limit_order(){
  order_limit(props.symbol,quantity.value)
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
    console.log("TradeConsole → task ordine:", order);
    // [{"step": 1, "side": "BUY", "op": "last >", "price": 4.716045518354935, "quantity": 100.0, "desc": "MARKER", "state": "filled", "trigger_price": 4.7595}, {"step": 2, "side": "SELL", "op": "last >", "price": 5.542954152014922, "quantity": 100.0, "desc": "TP"}, {"step": 2, "side": "SELL", "op": "last <", "price": 4.287409154718572, "quantity": 100.0, "desc": "SL"}]
    active_order_task.value='...'

    if (order.status == "READY" || order.status == "STEP" )
    {
      let sum=""
      let selected =""
      order.data.forEach( (step)=>{
        if (step.step == order.step){
          console.log("selected ",step );
          selected+= `
          <span class="badge step">${step.step}</span>
            <span class="side sell">${step.side}</span>
            <span class="qty">${step.quantity}</span>
            <span class="cond">
              ${step.op}<b>${step.price.toFixed(6)}</b>
            </span>
            <span class="tag tp">${step.desc}</span>
          `;
        }
        sum += `(${step.step}) ${step.side} ${step.quantity} @ ${step.op}${step.price.toFixed(6)} \n`
      });

      active_order_task.value =`
        <div class="trade-main" title="
    
  ${sum}
    ">
    ${selected}
    </div>
      `
  }
    /*
    const aa =`
     <div class="trade-main" title="
STEP 1 • BUY 100 @ last > 4.7160 (MARKER) [filled]

STEP 2 • SELL 100 @ last > 5.5430 (TP)
STEP 2 • SELL 100 @ last < 4.2874 (SL)
  ">
    <span class="badge step">STEP 2</span>

    <span class="side sell">SELL</span>
    <span class="qty">100</span>

    <span class="cond">
      last &gt; <b>5.5430</b>
    </span>

    <span class="tag tp">TP</span>
  </div>
  `;
  */
  }
}

function onOrderReceived(msg) {
  
  if (msg.symbol == props.symbol)
  {
     //console.log("onOrderReceived", msg)
    if (msg.event_type == "STATUS" && ( msg.status === "Filled" || msg.status === "Submitted" ||  msg.status === "Cancelled") )
    {
      let icon = `🧾`;
      if (msg.status =="Filled")  icon = `✔️`;
      if (msg.status =="Submitted")  icon = `⏱`;
      if (msg.status =="Cancelled")  icon = `❌`;
      let color = "red"
      if (msg.action =="BUY") color ="green"

      active_order.value =`${icon} <strong style='color:${color}'>${msg.action}</strong>  filled:${msg.filled}/${msg.totalQuantity }  (<strong style='color:blue'>${msg.status}</strong>) `;
   
    }
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

function onTradeUpdated(msg){
 //  console.log("..",props.symbol,msg.data)
 if (msg.data.symbol === props.symbol)
   {
    // console.log("...",msg.data)
      tradeList.value.push(msg.data)
  }
}

onMounted( async () => {
  eventBus.on("task-order-received", onTaskOrderReceived);
  eventBus.on("order-received", onOrderReceived);
  eventBus.on("ticker-received", onTickerReceived);
  eventBus.on("update-portfolio", onPositionUpdated);
  eventBus.on("update-position", onPositionUpdated);
  eventBus.on("trade-position", onTradeUpdated);
   
  let pos_list = await send_get('/account/positions')
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
  eventBus.off("trade-position", onTradeUpdated);
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

<style scoped>

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

.position-badge {
  background: #ffffff;
  color: #000000;
  padding: 6px 12px;
  border-radius: 8px;
  font-weight: 600;
  letter-spacing: 0.5px;
  font-size: 0.9rem;
  box-shadow: 0 4px 10px rgba(0,0,0,0.25);
  border: 1px solid #334155;
}


.position-main {
  background: #4998ff; /* più scuro */
  font-weight: bold;
}

.trade-box {
  position: relative;
  display: inline-block;
  padding: 6px;
  border: 1px solid #444;
  background: #111;
  color: white;
  cursor: pointer;
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


.trade-box {
  font-family: system-ui;
  font-size: 13px;
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

.badge.step {
  background: #1e293b;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 600;
}

.side.buy { color: #22c55e; font-weight: 700; }
.side.sell { color: #ef4444; font-weight: 700; }

.qty {
  opacity: 0.8;
}

.cond {
  opacity: 0.9;
}

.tag.tp {
  background: #16a34a;
  color: white;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 11px;
}

.tag.sl {
  background: #dc2626;
  color: white;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 11px;
}

.tag.marker {
  background: #3b82f6;
  color: white;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 11px;
}
</style>