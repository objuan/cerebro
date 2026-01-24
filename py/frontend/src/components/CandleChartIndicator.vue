<template>
  <div v-if="showIndicatorModal" class="indicator-modal-backdrop">
  <div class="indicator-modal">

    <h5>Add Indicator</h5>

    <div class="form-group">
      <label>Indicator</label>
      <select v-model="selectedIndicator" class="form-select">
        <option value="SMA">SMA</option>
        <option value="EMA">EMA</option>
        <option value="RSI">RSI</option>
        <option value="MACD">MACD</option>
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
import { applyEMA, applySMA } from '@pipsend/charts'; //createTradingLine

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

function addIndicator(context,ind){
    console.log("onAddIndicator ",ind)
    let serie =null;
    if (ind.type =="SMA")
    {
      serie = applySMA(context.series.main, context.charts.main, { 
        period: ind.params.period, 
        color: ind.params.color,
      });

      serie.applyOptions({
        priceLineVisible: false,
        lastValueVisible: false,
        lineWidth: 1,
      });
   }
   if (ind.type =="EMA")
    {
      serie = applyEMA(context.series.main, context.charts.main, { 
        period: ind.params.period, 
        color: ind.params.color,
      });
      serie.applyOptions({
        priceLineVisible: false,
        lastValueVisible: false,
        lineWidth: 1,
      });
  }

  console.log("add serie",serie)
  //context.charts.main.removeSeries(serie)
  return {"type" : ind.type.toUpperCase() ,"serie":  serie, "params" : 
  {
      "color" : ind.params.color,  
      "period" : ind.params.period, "overbought" : ind.params.overbought, "oversold" : ind.params.oversold, 
     }
  };
  
}

defineExpose({
  open,
  addIndicator
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

