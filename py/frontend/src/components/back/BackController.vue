<template>
  <div class="time-player">

    <button @click="play">▶</button>
    <button @click="stop">⏹</button>
    <button @click="stepForward">⏭</button>

    <input
      :key="maxIndex"
      type="range"
      :min="0"
      :max="maxIndex"
      v-model.number="currentIndex"
      @input="emitChange"
      class="slider"
    />

    <div class="info">
      {{ formattedCurrent }}
    </div>

  </div>
</template>

<script setup>
import { ref, computed,  onUnmounted } from "vue"
import {localUnixToUtc,formatDate, send_get} from '@/components/js/utils.js';

let data = []
//const stepMs = ref(null)
let intervalMs = null

const maxIndex = ref(null)
const currentIndex = ref(0)

let timer = null

// DATA LOCALE

function setup(_data,_stepMs,_intervalMs ){
  
  data = Array.isArray(_data) ? _data : []
  intervalMs = (_intervalMs || 1) * 1000

  maxIndex.value = Math.max(data.length - 1, 0)
  currentIndex.value = maxIndex.value

  //console.log("setup",data,"e",_stepMs,_intervalMs,"max ",currentIndex.value)
}

const emit = defineEmits(["update:current", "play", "stop"])

function getTime(t)
{
//  console.log(currentIndex.value)
  t = localUnixToUtc(t)
  return formatDate(new Date(t*1000))
}

const currentTimestamp = computed(() =>
{
  if (data[currentIndex.value ])
{
     //  console.log(data[currentIndex.value ].time)
       return data[currentIndex.value ].time;
}
  else
    return 0;
}
  //data.value[currentIndex.value ].time
  //dt_start.value + currentIndex.value * stepMs.value
)

const formattedCurrent = computed(() =>
  getTime(currentTimestamp.value)
)

// ========

function emitChange() {
  send_get("/back/trade/currentTime", {current: localUnixToUtc(currentTimestamp.value)})
  emit("update:current", localUnixToUtc(currentTimestamp.value))
}

function play() {
  if (timer) return

  emit("play")

  timer = setInterval(() => {
    if (currentIndex.value < maxIndex.value) {
      currentIndex.value++
      emitChange()
    } else {
      stop()
    }
  }, intervalMs.value)
}

function stop() {
  emit("stop")
  clearInterval(timer)
  timer = null
}

function stepForward() {
  if (currentIndex.value < maxIndex.value) {
    currentIndex.value++
    emitChange()
  }
}

onUnmounted(() => {
  stop()
})

defineExpose({
  setup,
});


</script>

<style scoped>
.time-player {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 40px;
  padding: 0 10px;
  background-color: rgb(80, 80, 80);
}

button {
  padding: 4px 8px;
  cursor: pointer;
}

.slider {
  flex: 1; /* prende tutto lo spazio centrale */
}

.info {
  min-width: 160px;
  font-size: 14px;
  text-align: right;
}
</style>