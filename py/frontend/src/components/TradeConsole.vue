<template>
 
  <div class="trade-root">
    <div class="trade-grid">
      <!-- left-->
       <div class="col-2rows">
          <div class="row r1">
                <div class="d-flex align-items-center gap-1">
                  {{symbol}} Quantity
                  <select
                    v-model="quantity"
                    class="form-select form-select-sm"
                    style="width: 80px"
                  >
                    <option :value="100">100</option>
                    <option :value="200">200</option>
                    <option :value="300">300</option>
                    <option :value="400">400</option>
                    <option :value="500">500</option>
                    <option :value="600">600</option>
                    <option :value="700">700</option>
                    <option :value="800">800</option>
                    <option :value="900">900</option>
                    <option :value="1000">1000</option>
                    <option :value="1500">1500</option>
                    <option :value="2000">2000</option>
                  </select>
                </div>
          </div>
         <div class="row r2">
            <div class="d-flex align-items-center gap-1">
                  <button class="btn btn-sm "
                      :class="tradeMode === 'DIRECT' ? 'btn-success active-mode' : 'btn-outline-success'"
                        @click="setMode('DIRECT')">DIRECT</button>

                  <button class="btn btn-sm "
                        :class="tradeMode === 'MARKER' ? 'btn-success active-mode' : 'btn-outline-success'"
                        @click="setMode('MARKER')" >MARKER</button>
              </div>
          </div>
          
      </div>  
      <!-- mid-->
        <div class="col-2rows">
           <div class="row r1">
                  <div class="d-flex align-items-center gap-0" v-if="tradeMode=='DIRECT'">
                    <button    class="btn btn-sm btn-success"
                          @click="send_limit_order()"
                        >BUY</button>

                     <div class="flex-grow-1 text-center">
                          Buy <strong>{{ quantity }}</strong> at 
                          <strong>{{ ticker?.last.toFixed(2) }}</strong> 
                            = ${{ (quantity * ticker?.last).toFixed(1) }}     
                     
                    </div>
                    <div  v-if="lastTrade && lastTrade.isOpen">
                           (OPEN)
                    </div>

                  </div>
                  <div class="d-flex align-items-center gap-1" v-if="tradeMode=='MARKER' && isCurrent">
                    <table class="trade-info-panel" >
                        <tr>
                          <td> 
                            <button  class="btn btn-sm btn-success"
                                @click="send_order_marker()"
                              >SEND {{ tradeData.type }} {{ tradeData.timeframe }} </button>
                          </td>
                          <td>
                            <table style="width:100%;height:40px">
                              <tr>
                                 
                                  <td colspan="2">
                                    BUY <strong style="color:yellow">{{ Number(tradeData.total_price_usd).toFixed(2) }} $</strong>
                                      ({{ Number(tradeData.price).toFixed(2) }}x{{ tradeData.quantity }})
                                  </td>
                                 
                              </tr>
                              <tr>
                                 <td style="color:lime;width: 50%;">
                                    GAIN <strong>{{ Number(tradeData.profit_usd).toFixed(1) }}</strong>
                                </td>
                                <td style="color:red;width: 50%;">
                                    LOSS <strong>{{ Number(tradeData.loss_usd).toFixed(1) }} $</strong>
                                </td>
                              </tr>
                            </table>
                          </td>
                        </tr>
      
                    </table>
                    
                 
                  </div>
            </div>
            <div class="row r2">
                <div v-if="isCurrent" style="position: relative">
                      <div class="me-2" style="position: absolute; left:55px">
                        <i v-if="isUpdating" class="spinner-border spinner-border-sm text-primary rotating"></i>
                      </div>
                      <div class="me-2" style="position: absolute;left:6px">
                            <button  class="task-cancel-button btn btn-sm btn-outline-danger ms-1"  title="Delete Marker Trade"
                                  @click="cancelTaskOrder()">
                                  ❌
                                </button>
                      </div>
                      <div class="active-task  p-1 d-flex justify-content-between align-items-center">
                          <div  v-html="active_order_task"></div>
                      </div>
                 </div>
                
              </div>
      </div>  

     <!-- sell-->

     <button class="btn btn-sm btn-danger" @click="clear_all()"  >SELL ALL</button>

      <!-- right-->
      <TradeHistoryWidget :symbol="props.symbol"  style="width:100%"></TradeHistoryWidget>
          
    </div>


  </div>
</template>

<script setup>


import { ref,watch,computed,onMounted,onBeforeUnmount  } from 'vue';
import { liveStore } from '@/components/js/liveStore.js'; // Assicurati che il percorso sia corretto
import { staticStore } from '@/components/js/staticStore.js';
import {send_post} from '@/components/js/utils.js'
import { eventBus } from "@/components/js/eventBus";
import {order_limit,clear_all_orders,order_bracket,order_tp_sl} from "@/components/js/orderManager";
import  TradeHistoryWidget  from './TradeHistoryWidget.vue'
import { tradeStore } from "@/components/js/tradeStore";

//events
const emit = defineEmits(['cancel-task-order']);

// props
const props = defineProps({
  symbol: { type: String, required: true },
});
watch(() => props.symbol, () => {
  //console.log("symbol cambiato:", newValue);

    quantity.value = staticStore.get(get_key("quantity"),100);  
    tradeMode.value = staticStore.get(get_key("mode"),"DIRECT");  
});

// 
const get_key = (subkey)=> { return `symbols.${props.symbol}.${subkey}`}


const tradeMode = ref("DIRECT");
const tradeData = ref(null);
const quantity = ref(0);
const ticker = ref(null);
const isUpdating = ref(false)
const active_order_task = ref("");

let updateTimer = null

// =========

const liveData = computed(() => liveStore.state.dataByPath);

const isCurrent = computed(() => {
  return tradeData.value && tradeData.value.symbol == props.symbol;
});

const lastTrade = computed(() => {
  return tradeStore.lastTrade(props.symbol);
})


// =========

function setMode(mode){
  tradeMode.value=mode;
   staticStore.set(get_key("mode"),mode );  
}

function send_limit_order(){
  // check 
  if(lastTrade.value && lastTrade.value.isOpen){
    const ok = confirm("Hai già una posizione aperta. Vuoi continuare?")
    if(!ok) return
  }

  order_limit(props.symbol,quantity.value)
}



function send_order_marker(){

  console.log("send_order_marker", tradeData.value);  

  if (tradeData.value.type == "tp_sl") 
    order_tp_sl(props.symbol,tradeData.value.timeframe,tradeData.value.take_profit, tradeData.value.stop_loss )
  else
    order_bracket(props.symbol,tradeData.value.timeframe,quantity.value,ticker.value.last )
}


function clear_all(){
  clear_all_orders(props.symbol);
}

async function cancelTaskOrder(){
   emit('cancel-task-order',tradeData.value.timeframe ) 

} 

function onTaskOrderReceived(order){
  if (order.symbol == props.symbol)
  {
    console.log("TradeConsole → task ordine:", order);
    // [{"step": 1, "side": "BUY", "op": "last >", "price": 4.716045518354935, "quantity": 100.0, "desc": "MARKER", "state": "filled", "trigger_price": 4.7595}, {"step": 2, "side": "SELL", "op": "last >", "price": 5.542954152014922, "quantity": 100.0, "desc": "TP"}, {"step": 2, "side": "SELL", "op": "last <", "price": 4.287409154718572, "quantity": 100.0, "desc": "SL"}]
    active_order_task.value=''

    if (order.status == "READY" || order.status == "STEP" )
    {
      let sum=""
      let selected =""
      order.data.forEach( (step)=>{
        if (step.step == order.step){
          console.log("selected ",step );
          let col ="red";
          if (step.desc == "TP") col="green";  

          if (selected.length>0) selected+=`<br>` 
          selected+= `
          <span class="step">(${step.step})</span>
            <span style="color:${col}">${step.desc}</span>
           
            <span class="side sell">${step.side}</span>
            <span class="qty">${step.quantity}</span>
            <span class="cond">
              ${step.op}<b>${step.price.toFixed(4)}</b>
            </span>
         
          `;
        }
        sum += `(${step.step}) ${step.side} ${step.quantity} @ ${step.op}${step.price.toFixed(4)} \n`
      });

      active_order_task.value =`<div class="trade-main" title="
          ${sum}
            ">
            ${selected}
            </div>
         `
      
  }

  }
}

function triggerUpdateIcon() {
  isUpdating.value = true
 
  // reset timer se arrivano molti eventi ravvicinati
  if (updateTimer) clearTimeout(updateTimer)

  updateTimer = setTimeout(() => {
    isUpdating.value = false
  }, 1000) // durata visibilità icona
  
}

function onTaskOrderMsgReceived(order){
  if (order.symbol == props.symbol)
  {
    triggerUpdateIcon();
    //console.log("TradeConsole → task ordine msg:", order,updateTimer);
   
      
  }
} 

/*
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
*/
function onTickerReceived(_ticker) {
  if (_ticker.symbol == props.symbol)
  {
   // console.log("TradeConsole → ticker:", _ticker);
    ticker.value =_ticker
  }
}
/*
function onPositionUpdated(msg){
   if (msg.symbol == props.symbol)
   {
      position.value = msg.position
  }
}

function onTradeUpdated(msg){
   console.log("onTradeUpdated ",props.symbol,msg)
  
 if (msg.symbol === props.symbol)
   {
    // console.log("...",msg.data)
      tradeList.value.push(msg)
  }
      
}
*/

onMounted( async () => {
  eventBus.on("task-order-received", onTaskOrderReceived);
  //eventBus.on("order-received", onOrderReceived);
  eventBus.on("ticker-received", onTickerReceived);
  eventBus.on("task-order-msg-received", onTaskOrderMsgReceived);

  eventBus.on("on-start", ()=>{
    //console.log("TradeConsole on-start", props.symbol,quantity.value );
    quantity.value = staticStore.get(get_key("quantity"),100);  
    tradeMode.value = staticStore.get(get_key("mode"),"DIRECT");  
    
  });

});

onBeforeUnmount(() => {
  eventBus.off("task-order-received", onTaskOrderReceived);
 // eventBus.off("order-received", onOrderReceived);
  eventBus.off("ticker-received", onTickerReceived);

  eventBus.off("task-order-msg-received", onTaskOrderMsgReceived);

 // eventBus.off("update-portfolio", onPositionUpdated);
 // eventBus.off("update-position", onPositionUpdated);
 // eventBus.off("trade-position", onTradeUpdated);
});

// ========================

// sync STORE → SELECT

watch(
  () =>
  {
    return liveData.value['trade.tradeData.'+props.symbol];
  } ,
  v => {
  //  console.log("TradeConsole watch tradeData", props.symbol, v); 

    //if (v != null) 
        tradeData.value = v;
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
     //console.log("quantity",newValue, oldValue)

     staticStore.set(get_key("quantity"),quantity.value );  

    if (tradeData.value == null) return;

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

.rotating {
  z-index: 100;
  /*left:2;
  top:10;*/
  position: absolute;
  animation: spin 0.8s linear infinite;
}
.task-cancel-button {
  z-index: 90;
  
  
  position: absolute;
}


@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.active-task{
  color:rgb(255, 255, 255);
  font-family: monospace;
  font-size: 13px;
  margin-left: 42px;
  border : solid #d9ff00 1px;
  height: 100%;
}
.trade-root{
  height: 100%  ;
}
.trade-info-panel{
  width: 100%;
  height: 50%;
  font-family: monospace;
  font-size: 13px;
  border:#e2e8f0 1px solid;
}
table td:first-child {
  text-align: left;
  padding-right: 10px;
}

table td {
  text-align: right;
}

.trade-grid {
  display: grid;
  grid-template-columns: 160px calc(50% - 240px) 80px 50%;
  gap: 2px;
  width: 100%;
  align-items: start;
  height: 100%;
}
/* Le colonne left e mid diventano "trasparenti" alla grid padre */
.col-2rows {
  height: 100%;
}

/* Posizioniamo le righe nella grid principale */
.r1 { grid-row: 1; height: 50%; }
.r2 { grid-row: 2;height: 50%; }

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