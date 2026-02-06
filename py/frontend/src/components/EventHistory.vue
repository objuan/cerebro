<template>
 
   <div class="p-0">
    <div class="overflow-x-auto">
      <div
        v-for="t in store.items"
        :key="t.id"
        class="toast"
        :class="t.type"
      >
         <div :class="['header', t.subtype]">
          <div class="time">
            {{ new Date(t.ts).toLocaleTimeString() }}
          </div>
          <span class="icon">{{ iconMap[t.type] }}</span>
          <span class="title">{{ titleMap[t.type] }}</span>
           <span class="title ms-auto" style="color:yellow"> {{ t.symbol}}</span>
        </div>
   
         <div
            class="msg"
            v-html="t.message"
          />
      </div>

    </div>
</div>

</template>

<script setup>
import {  } from 'vue'
import { eventStore as store } from "@/components/js/eventStore";

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

</script>

<style scoped>

.body {
  overflow-y: auto;
  max-height: 60vh;
}

.row {
  padding: 8px 10px;
  border-bottom: 1px solid #1e293b;
  font-size: 13px;
}

.row.error { border-left: 4px solid #ef4444; }
.row.warning { border-left: 4px solid #f59e0b; }
.row.info { border-left: 4px solid #3b82f6; }

.time {
  font-size: 16px;
  opacity: 1.6;
  margin-bottom: 4px;
}

.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 99999;
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none;
}

.toast {
   display: block;
  pointer-events: auto;
  min-width: 300px;
  max-width: 420px;
  padding: 14px 16px;
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


</style>