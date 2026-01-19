<template>
  <header class="py-1 mb-1 border-bottom bg-light">


    <div class="card-body p-2 d-flex justify-content-between align-items-center">
          
        <div class="fw-bold">Balance {{ liveData['balance.USD'] }}</div>
        <div class="fw-bold">Max DayLoss {{ liveData['trade.max_day_loss'] }}</div>
        <div class="fw-bold">Trade DayLoss {{ liveData['trade.risk_per_trade'] }}</div>

    </div>
    <div class="card-body p-2 d-flex justify-content-between align-items-center">
        <div class="fw-bold d-flex align-items-center gap-1">
          Trade Risk
          <input
            type="number"
            step="0.01"
            class="form-control form-control-sm"
            style="width: 90px"
            v-model.number="tradeRisk"
          />
        </div>

        <div class="fw-bold d-flex align-items-center gap-1">
          Day Risk
          <input
            type="number"
            step="0.01"
            class="form-control form-control-sm"
            style="width: 90px"
            v-model.number="dayRisk"
          />
        </div>

        <div class="fw-bold">
            RR {{ displayRR }}
        </div>

        <select
          v-model="rr"
          class="form-select form-select-sm"
          style="width: 80px"
        >
          <option :value="2">2:1</option>
          <option :value="3">3:1</option>
          <option :value="4">4:1</option>
        </select>


    </div>

  </header>
</template>

<script setup>


import { ref,computed,watch  } from 'vue';
import { liveStore } from '@/components/js/liveStore.js'; // Assicurati che il percorso sia corretto
import {send_post} from '@/components/js/utils.js'

const rr = ref(1);
const tradeRisk = ref(null);
const dayRisk = ref(null);

// Esponiamo i dati dello store al template
const liveData = computed(() => liveStore.state.dataByPath);
const displayRR = computed(() => {
  const v = liveData.value['trade.rr'] ?? rr.value ?? 1;
  return v + ':1';
});


// sync STORE → SELECT

watch(
  () => liveData.value['trade.trade_risk'],
  v => {
    if (v != null) tradeRisk.value = v;
  },
  { immediate: true }
);

watch(
  () => liveData.value['trade.day_risk'],
  v => {
    if (v != null) dayRisk.value = v;
  },
  { immediate: true }
);

watch(
  () => liveData.value['trade.rr'],
  v => {
    if (v != null) rr.value = v;
  },
  { immediate: true }
);

/* =========================
   INPUTS → STORE + SAVE
   ========================= */

watch(rr, async (newValue, oldValue)  => {
  if (newValue == null) return;
  if (oldValue && oldValue!= newValue)
  {
    liveStore.updatePathData('trade.rr', newValue);
    send_post('/api/props/save', { path: 'trade.rr', value: newValue });
  }
});

watch(tradeRisk, async (newValue, oldValue)  => {
  if (newValue == null) return;
   if (oldValue && oldValue!= newValue)
  {
    liveStore.updatePathData('trade.trade_risk',newValue);
    send_post('/api/props/save', { path: 'trade.trade_risk', value: newValue});
  }
});

watch(dayRisk, async (newValue, oldValue)  => {
  if (newValue == null) return;
   if (oldValue && oldValue!= newValue)
  {
    liveStore.updatePathData('trade.day_risk', newValue);
    send_post('/api/props/save', { path: 'trade.day_risk', value: newValue });
  }
});


</script>