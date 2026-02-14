<template>
  <Teleport to="body">
    <transition-group name="toast" tag="div" class="toast-container">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="toast"
        :class="t.type"
        @click="remove(t.id)"
      >
       <div :class="['header', t.subtype]">
          <span class="icon">{{ iconMap[t.type] }}</span>
          <span class="title">{{ titleMap[t.type] }}</span>
          <span class="title"> {{ t.subtype}}</span>
          <span class="title ms-auto" style="color:yellow"> {{ t.symbol}}</span>
        </div>
   
         <div class="msg"   v-html="t.message"   />
      </div>
    </transition-group>
  </Teleport>
</template>

<script setup>
import { ref,onMounted,onBeforeUnmount } from 'vue'
import { eventBus } from "@/components/js/eventBus";
import { eventStore as store } from "@/components/js/eventStore";

const toasts = ref([])

const iconMap = {
  error: "⛔",
  warning: "⚠",
  info: "ℹ"
}

const titleMap = {
  error: "Errore",
  warning: "Attenzione",
  info: "Info"
}

function addToast(ts,source,icon, symbol,summary, message, type,subtype,color) {

//   console.log("addToast", source,ts,message,type)
  const  dt = new Date(ts)
  const diffSeconds = (Date.now() - dt.getTime()) / 1000
  //console.log("diffSeconds",dt, diffSeconds,source)

  const id = Date.now() + Math.random()
  const toast = { ts, source,id, icon, symbol,summary, message, type,subtype, color }

  store.push(toast);

  if (diffSeconds < 10)
  {
    // check time
    toasts.value.push(toast)

    setTimeout(() => remove(id), 6000)
  }
}

function remove(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

const STATUS_COLORS = {
  Filled:    "#b6f5c2",
  Submitted: "#fff3b0",
  Cancelled: "#ffb3b3",
  default:   "#e0e0e0"
}

function onOrderReceived(msg) {

    if (msg.event_type == "STATUS" && ( msg.status === "Filled" || msg.status === "Submitted" ||  msg.status === "Cancelled") )
    {  
      //console.log("onOrderReceived",msg)
  
      let icon = `🧾`;
      
      if (msg.status =="Filled")  icon = `✔️`;
      if (msg.status =="Submitted")  icon = `⏱`;
      if (msg.status =="Cancelled")  icon = `❌`;

      let color = STATUS_COLORS[msg.status]

      const  summary =`${ msg.action } ${msg.filled}/${msg.totalQuantity } ${msg.status} `;

      const  smsg =`${ msg.action } filled:${msg.filled}/${msg.totalQuantity } <br> price: ${msg.lmtPrice} <br> state:${msg.status} `;

      addToast(msg.ts, "order",icon,msg.symbol,summary, smsg, "info","order",color)
    }
}

function onTaskOrderReceived( msg) {
  try {
    console.log("onTaskOrderReceived",msg);

    msg.data.forEach( (step)=>{
      if (step.step == msg.step){

          const  summary =`${msg.status } ${step.desc} `;

          const smsg =`${msg.status}  <br> ${step.desc} (${step.step}) ${ step.side } ${step.quantity } <br>${ step.op } ${ step.price } `;
          addToast(msg.ts,"task-order","",msg.symbol, summary, smsg, "info","task","#aab3b3" )
      }
    });
       
  } catch (e) {
    console.error("Orders parse error", e);
  }
}


onMounted( async () => {

  eventBus.on("order-received", onOrderReceived);
  eventBus.on("task-order-received", onTaskOrderReceived);

  // ====================

  eventBus.on("error-received", (payload) => {
    const msg = "("+payload.errorCode+") " +payload.errorString
    addToast(payload.ts,"error", `❌`,payload.symbol,msg, msg, "error","general", "#AA3333")
  })

  eventBus.on("warning-received", (payload) => {
      const msg = "("+payload.errorCode+") " +payload.errorString
    addToast(payload.ts,"warn", `⚠`, payload.symbol,msg,msg, "warning","general","#AA3333")
  })

  eventBus.on("message-received", (payload) => {
      const msg = "("+payload.errorCode+") " +payload.errorString
    addToast(payload.ts,"message",`🧾`,payload.symbol,msg,msg,"info","general","#888888")
  })

});

onBeforeUnmount(() => {
  
});

</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 2px;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none;
}

.toast {
   display: block;
  pointer-events: auto;
  width:200px;
  padding: 2px 2px;
  border-radius: 10px;
  color: #fff;
  box-shadow: 0 10px 30px rgba(0,0,0,0.35);
  font-family: system-ui;
  animation: fadein 0.2s ease;
  cursor: pointer;
  border-left: 6px solid transparent;
}

.toast .header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 6px;
}

.toast .msg {
  font-size: 0.9rem;
  opacity: 0.95;
}

/* TIPI */

.toast.error {
  background: #1f2937;
  border-left-color: #ef4444;
}

.toast.warning {
  background: #1f2937;
  border-left-color: #f59e0b;
}

.toast.info {
  background: #1f2937;
  border-left-color: #3b82f6;
}

.order {
  background: #307927;
  border-left-color: #3b82f6;
}

.task {
  background: #3a2a68;
  border-left-color: #3b82f6;
}
.general {
  background: #6d2026;
  border-left-color: #3b82f6;
}

/* Animazioni */

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(60px);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}

@keyframes fadein {
  from { opacity: 0; transform: translateX(40px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
