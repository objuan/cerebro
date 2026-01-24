<template>
  <div class="dropdown" ref="root">
    <button class="btn btn-sm btn-primary" @click="toggle">
      {{ label }} ▾
    </button>

    <div v-if="open" class="dropdown-menu">
      <div
        v-for="item in props.items"
        :key="item.key"
        class="dropdown-item"
        @click="onItemClick(item)"
      >
        {{ item.text }}
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, onMounted, onBeforeUnmount ,defineProps } from 'vue';

const props = defineProps({
  label: { type: String, default: 'Menu' },
  items: { type: Array, required: true }
});

const emit = defineEmits(['select']);

const open = ref(false);
const root = ref(null);

function toggle() {
  console.log("toggle",props.items)
  open.value = !open.value;
}

function onItemClick(item) {
  emit('select', item);
  open.value = false;
}

function handleClickOutside(e) {
  if (root.value && !root.value.contains(e.target)) {
    open.value = false;
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<style scoped>
.dropdown {
  position: relative;
  display: inline-block;
}

.dropdown-menu {
  position: absolute;
  top: 110%;
  left: 0;
  background: white;
  border: 1px solid #ccc;
  border-radius: 6px;
  min-width: 180px;
  box-shadow: 0 4px 10px rgba(0,0,0,0.15);
  z-index: 1000;
    display: block;
}

.dropdown-item {
  padding: 8px 12px;
  cursor: pointer;
  display: block;
}

.dropdown-item:hover {
  background: #f2f2f2;
}
</style>
