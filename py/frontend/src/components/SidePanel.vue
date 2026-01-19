<template>
  <!-- Overlay -->
   <div>
  <div
    v-if="isOpen"
    class="overlay"
    @click="close"
  ></div>

  <!-- Side panel -->
  <aside
    class="panel"
    :class="{ open: isOpen }"
  >
    <header class="panel-header">
      <h2>📊 {{title}}</h2>
      <button class="close-btn" @click="close">✕</button>
    </header>

    <div class="panel-content">
      <slot />
    </div>

  </aside>
  </div>
</template>

<script setup>
import {   ref,onMounted,onBeforeUnmount } from "vue";

defineProps(
  {
  title: { 
    type: String,required: true, default: 'TODO'
  },
   width: { 
    type: String,required: false, default: '420px'
  }
})


const isOpen = ref(false);


/* ====== API pubblica ====== */
function open() {
  isOpen.value = true;
}

function close() {
  isOpen.value = false;
}

function toggle() {
  isOpen.value = !isOpen.value;
}

defineExpose({
  open,
  close,
  toggle,
});


onMounted(async () => {
});

onBeforeUnmount(() => {
});


</script>

<style scoped>
/* Overlay */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 90;
}

/* Panel */
.panel {
  position: fixed;
  top: 0;
  right: calc(-1 * v-bind(width));
  width: v-bind(width);
  height: 100vh;
  background: #ffffff;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.2);
  transition: right 0.3s ease;
  z-index: 100;
  padding: 1rem;
  display: flex;
  flex-direction: column;
}

.panel.open {
  right: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.4rem;
  cursor: pointer;
}

.empty {
  color: #777;
  margin-top: 1rem;
}
</style>