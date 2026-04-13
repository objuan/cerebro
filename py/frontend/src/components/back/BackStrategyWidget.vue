<template>
  <div class="strategy-editor" v-if="backTest.inData">
    <!-- Budget -->
    <div class="field">
      <label>Budget</label>
      <input
        type="number"
        v-model.number="form.badgetUSD"
        min="0"
        class="input"
      />
    </div>

    <!-- Strategy Select -->
    <div class="field">
      <label>Strategy</label>
      <select v-model="selectedStrategyIndex" class="input">
        <option
          v-for="(strategy, index) in strategies"
          :key="index"
          :value="index"
        >
          {{ strategy.module }} - {{ strategy.class }}
        </option>
      </select>
    </div>

    <!-- Timeframe -->

     <div class="field">
      <label>Timeframe</label>
      <select 
          v-model="currentTimeframe" 
          @change="onTimeFrameChange" 
          class="form-select form-select-sm bg-dark text-white border-secondary timeframe-selector"
        >
          <option value="10s">10s</option>
          <option value="30s">30s</option>
          <option value="1m">1m</option>
          <option value="5m">5m</option>
          <option value="1h">1h</option>
          <option value="1d">1d</option>
        </select>
    </div>


    <!-- Params JSON -->
    <div class="field">
      <label>Params (JSON)</label>
      <textarea
        v-model="paramsText"
        rows="8"
        class="textarea"
      ></textarea>
      <div v-if="jsonError" class="error">
        {{ jsonError }}
      </div>
    </div>

    <!-- Save Button -->
    <button @click="onSave" :disabled="jsonError" class="button">
      Save
    </button>
    <button @click="execute" :disabled="jsonError" class="button">
      Execute
    </button>
  </div>
</template>

<script setup>
import { ref,   onMounted, watch, computed } from "vue"
import {send_get} from  "@/components/js/utils";
import {backTest} from "@/components/back/backtest";
//const emit = defineEmits(["save"])


const strategies = ref([])
const selectedStrategyIndex = ref(null)
const currentTimeframe = ref("1m")

const form = computed(() => {
  return backTest.inData
});

/*
const form = reactive({
  budget: 1000,
  module: "",
  class: "",
  timeframe: 0,
  params: {}
})
  */

const paramsText = ref("{}")
const jsonError = ref(null)

function onTimeFrameChange(){
    backTest.inData.tf=    currentTimeframe.value
}

function onSave(){
    const strategy = strategies.value[selectedStrategyIndex.value]
 form.value.module = strategy.module
  form.value.class = strategy.class
    backTest.save()
}
function execute(){
    backTest.execute()
} 

onMounted(async () => {
  try {
    const data = await send_get("/back/strategy/list")

    console.log("strat list",data)
    strategies.value = data

    if (strategies.value.length > 0) {
      selectedStrategyIndex.value = 0
    }
  } catch (err) {
    console.error("Errore caricamento strategie:", err)
  }
})



watch(selectedStrategyIndex, (index) => {
  if (index === null) return

  const strategy = strategies.value[index]
  if (form.value)
{
  console.log("selected strategy", strategy)  
  form.value.module = strategy.module
  form.value.class = strategy.class
  //form.value.timeframe = strategy.timeframe
  //form.value.params =strategy.params // { ...strategy.params }

  paramsText.value = JSON.stringify(form.value.params, null, 2)
}
})
// TEXT → JSON
watch(paramsText, (value) => {
  try {
    const parsed = JSON.parse(value)
    form.value.params = parsed
    jsonError.value = null
  } catch (e) {
    jsonError.value = "JSON non valido"
  }
})
watch(
  () => form.value?.params,
  (value) => {
    if (!form.value) return

    const newText = JSON.stringify(value, null, 2)

    if (newText !== paramsText.value) {
      paramsText.value = newText
    }
  },
  { deep: true }
)

</script>

<style scoped>
.strategy-editor {
  max-width: 500px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
}

.input,
.textarea {
  padding: 8px;
  font-size: 14px;
}

.button {
  padding: 10px;
  cursor: pointer;
}

.error {
  color: red;
  font-size: 12px;
}
</style>