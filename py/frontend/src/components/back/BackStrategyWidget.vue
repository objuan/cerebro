<template>
  <div class="strategy-editor">

    <!-- Budget -->
    <div class="field">
      <label>Budget</label>
      <input
        type="number"
        v-model.number="form.budget"
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
      <input
        type="number"
        v-model.number="form.timeframe"
        class="input"
      />
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
    <button @click="emitSave" :disabled="jsonError" class="button">
      Salva
    </button>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from "vue"
import {send_get} from  "@/components/js/utils";

const emit = defineEmits(["save"])

const strategies = ref([])
const selectedStrategyIndex = ref(null)

const form = reactive({
  budget: 1000,
  module: "",
  class: "",
  timeframe: 0,
  params: {}
})

const paramsText = ref("{}")
const jsonError = ref(null)

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

  form.module = strategy.module
  form.class = strategy.class
  form.timeframe = strategy.timeframe
  form.params = { ...strategy.params }

  paramsText.value = JSON.stringify(form.params, null, 2)
})

watch(paramsText, (value) => {
  try {
    const parsed = JSON.parse(value)
    form.params = parsed
    jsonError.value = null
  } catch (e) {
    jsonError.value = "JSON non valido"
  }
})

function emitSave() {
  emit("save", { ...form })
}
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