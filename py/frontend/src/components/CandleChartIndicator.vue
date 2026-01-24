<template>
  <div v-if="showIndicatorModal" class="indicator-modal-backdrop">
  <div class="indicator-modal">

    <h5>Add Indicator</h5>

    <div class="form-group">
      <label>Indicator</label>
      <select v-model="selectedIndicator" class="form-select">
        <option value="sma">SMA</option>
        <option value="ema">EMA</option>
        <option value="rsi">RSI</option>
        <option value="macd">MACD</option>
      </select>
    </div>

    <div class="form-group" v-if="selectedIndicator">
      <label>Color</label>
      <input
        type="color"
        v-model="indicatorParams.color"
        class="form-control form-control-color"
      />
    </div>

    <div class="form-group" v-if="selectedIndicator">
      <label>Period</label>
      <input type="number" v-model.number="indicatorParams.period" class="form-control"/>
    </div>


    <div class="form-group" v-if="selectedIndicator === 'rsi'">
      <label>Overbought</label>
      <input type="number" v-model.number="indicatorParams.overbought" class="form-control"/>
      <label>Oversold</label>
      <input type="number" v-model.number="indicatorParams.oversold" class="form-control"/>
    </div>

    <div class="buttons">
      <button class="btn btn-primary" @click="confirmIndicator">Add</button>
      <button class="btn btn-secondary" @click="showIndicatorModal=false">Cancel</button>
    </div>

  </div>
</div>
</template>


<script setup>
import { ref } from 'vue';

const showIndicatorModal = ref(false)
const selectedIndicator = ref(null)
const emit = defineEmits(['add-indicator'])

const indicatorParams = ref({
  color: '#ffff00',   // 👈 default
  period: 14,
  overbought: 70,
  oversold: 30
})

function confirmIndicator() {
  emit('add-indicator', {
    type: selectedIndicator.value,
    params: { ...indicatorParams.value }
  })

  showIndicatorModal.value = false
}

function open(){
  showIndicatorModal.value=true
}

defineExpose({
  open,
});


</script>

<style scoped>
.indicator-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.indicator-modal {
  background: #1e1e1e;
  padding: 20px;
  border-radius: 8px;
  width: 320px;
  color: white;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>

