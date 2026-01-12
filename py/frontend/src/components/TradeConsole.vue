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
    </div>
  </div>
</template>

<script setup>


import { ref,watch,computed  } from 'vue';
import { liveStore } from '@/components/liveStore.js'; // Assicurati che il percorso sia corretto
import {send_post} from '@/components/utils.js'

const props = defineProps({
  symbol: { type: String, required: true },
});

const liveData = computed(() => liveStore.state.dataByPath);
const isCurrent = computed(() => {
  return tradeData.value && tradeData.value.symbol == props.symbol;
});
const tradeData = ref(null);
const quantity = ref(null);


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
});


</script>