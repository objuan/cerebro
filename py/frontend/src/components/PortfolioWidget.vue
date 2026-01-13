<template>
  <!-- Overlay -->
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
      <h2>📊 Portfolio</h2>
      <button class="close-btn" @click="close">✕</button>
    </header>

    <table v-if="rows.length">
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Position</th>
          <th>Avg Cost</th>
          <th>Market Price</th>
          <th>Market Value</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.symbol">
          <td>{{ row.symbol }}</td>
          <td>{{ row.position }}</td>
          <td>{{ format(row.avgCost) }}</td>
          <td>{{ format(row.marketPrice) }}</td>
          <td>{{ format(row.marketValue) }}</td>
        </tr>
      </tbody>
    </table>

    <p v-else class="empty">Nessuna posizione</p>
  </aside>
</template>

<script setup>
import { reactive, computed, ref } from "vue";

const isOpen = ref(false);

const portfolio = reactive({});

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

function handleMessage(msg) {
  try {
  
    if (!msg.symbol) return;

    if (!portfolio[msg.symbol]) {
      portfolio[msg.symbol] = {
        symbol: msg.symbol,
        position: 0,
        avgCost: null,
        marketPrice: null,
        marketValue: null,
      };
    }

    switch (msg.type) {
      case "POSITION":
        portfolio[msg.symbol].position = msg.position;
        portfolio[msg.symbol].avgCost = msg.avgCost;
        break;

      case "UPDATE_PORTFOLIO":
        portfolio[msg.symbol].position = msg.position;
        portfolio[msg.symbol].marketPrice = msg.marketPrice;
        portfolio[msg.symbol].marketValue = msg.marketValue;
        break;
    }
  } catch (e) {
    console.error("Portfolio parse error", e);
  }
}

defineExpose({
  open,
  close,
  toggle,
  handleMessage,
});

const rows = computed(() => Object.values(portfolio));

function format(value) {
  if (value == null) return "-";
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
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
  right: -420px;
  width: 420px;
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

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

th,
td {
  padding: 0.4rem;
  border-bottom: 1px solid #ddd;
  text-align: right;
}

th:first-child,
td:first-child {
  text-align: left;
}

.empty {
  color: #777;
  margin-top: 1rem;
}
</style>