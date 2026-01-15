<template>
  <div>
    <!-- Overlay -->
    <div
      v-if="open"
      class="overlay"
      @click="toggle()"
    />

    <!-- Panel -->
    <aside :class="['panel', { open }]">
      <header>
        <h2>📑 Orders</h2>
        <button @click="toggle()">✖</button>
      </header>

      <div class="filters">
          <button
            :class="{ active: viewMode === 'orders' }"
            @click="viewMode = 'orders'"
          >
            Orders
          </button>

          <button
            :class="{ active: viewMode === 'tasks' }"
            @click="viewMode = 'tasks'"
          >
            Tasks
          </button>

          <button @click="toggle()">✖</button>
        </div>

      <div class="content">
        <table v-if="visibleOrders.length">
          <thead>
            <tr>
               <th>Time</th>
              <th>Symbol</th>
              <th>Action</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Status</th>
            </tr>
          </thead>

          <tbody>
            <template v-for="o in visibleOrders" :key="o.trade_id">
              <tr @click="toggleDetails(o.id)">
                <td>{{ o.timestamp }}</td>
                <td>{{ o.symbol }}</td>
                <td>{{ o.action }}</td>
                <td>{{ o.totalQuantity }}</td>
                <td>{{ format(o.lmtPrice) }}</td>
                <td :class="statusClass(o.status)">
                  {{ o.status }}
                </td>
              </tr>

              <tr v-if="canExpand && expanded === o.id" class="details">
                <td colspan="5">
                  <div class="grid">
                    <div><b>OrderId:</b> {{ o.orderId }}</div>
                    <div><b>Filled:</b> {{ o.filled }}</div>
                    <div><b>Remaining:</b> {{ o.remaining }}</div>
                    <div><b>Avg:</b> {{ format(o.avgFillPrice) }}</div>
                  </div>

                  <ul class="log">
                    <li v-for="(l, i) in o.log" :key="i">
                      <span>{{ formatTime(l.time) }}</span>
                      <b>{{ l.status }}</b>
                      {{ l.message }}
                    </li>
                  </ul>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <p v-else class="empty">Nessun ordine</p>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { reactive, ref, computed,onMounted,onBeforeUnmount } from "vue";
import { eventBus } from "@/components/js/eventBus";

const viewMode = ref("orders"); 
const open = ref(false);
const expanded = ref(null);
const ordersMap = reactive({});
const task_ordersList = reactive([]);
//const emit = defineEmits(["order-received"]);
const canExpand = computed(() => viewMode.value === "orders");

const visibleOrders = computed(() => {
  if (viewMode.value === "orders") {
    return Object.values(ordersMap).sort(
      (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
    );
  }

  if (viewMode.value === "tasks") {
    return [...task_ordersList].sort(
      (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
    );
  }

  return [];
});

/* ===== PUBLIC API ===== */

function toggle() {
  open.value = !open.value;
}

function onOrderReceived(msg) {
  try {
    //console.log("onOrderReceived",msg)
    let dataParsed = msg["data"]

    ordersMap[msg.trade_id] = {
      ...msg,dataParsed
     // dataParsed,
    };
  } catch (e) {
    console.error("Orders parse error", e);
  }
}
function onTaskOrderReceived(msg) {
  try {
   // console.log("onTaskOrderReceived",msg);

    msg.totalQuantity = msg.data.totalQuantity
    msg.lmtPrice = msg.data.lmtPrice 
    task_ordersList.push(msg);
  } catch (e) {
    console.error("Orders parse error", e);
  }
}

defineExpose({ toggle });

/* ===== HELPERS ===== */
/*
const orders = computed(() =>
  Object.values(ordersMap).sort(
    (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
  )
);
*/

function toggleDetails(id) {
  expanded.value = expanded.value === id ? null : id;
}

function format(v) {
  return v == null ? "-" : Number(v).toFixed(2);
}

function formatTime(t) {
  return new Date(t).toLocaleTimeString();
}

function statusClass(s) {
  return {
    Filled: "ok",
    Cancelled: "err",
    Rejected: "err",
    Submitted: "warn",
  }[s] || "";
}

onMounted(() => {

  eventBus.on("order-received", onOrderReceived);
  eventBus.on("task-order-received", onTaskOrderReceived);
});

onBeforeUnmount(() => {
  eventBus.off("order-received", onOrderReceived);
  eventBus.off("task-order-received", onTaskOrderReceived);
});


</script>

<style scoped>
/* Overlay */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  z-index: 40;
}

/* Panel */
.panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 420px;
  height: 100%;
  background: #0f172a;
  color: #e5e7eb;
  transform: translateX(100%);
  transition: transform 0.25s ease;
  z-index: 50;
  display: flex;
  flex-direction: column;
}

.panel.open {
  transform: translateX(0);
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  border-bottom: 1px solid #1e293b;
}

header button {
  background: none;
  border: none;
  color: #e5e7eb;
  font-size: 1.2rem;
  cursor: pointer;
}

.content {
  padding: 0.5rem;
  overflow: auto;
}

table {
  width: 100%;
  font-size: 0.8rem;
  border-collapse: collapse;
}

th, td {
  padding: 0.3rem;
  border-bottom: 1px solid #1e293b;
}

.row:hover {
  background: #1e293b;
  cursor: pointer;
}

.details {
  background: #020617;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.3rem;
  margin-bottom: 0.3rem;
}

.log {
  list-style: none;
  padding: 0;
  font-size: 0.75rem;
}

.ok { color: #22c55e; }
.warn { color: #facc15; }
.err { color: #ef4444; }

.empty {
  padding: 1rem;
  color: #94a3b8;
}

.log {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 0.75rem;
}

.log li {
  display: flex;
  align-items: flex-start;   /* ✅ allinea in alto */
  justify-content: flex-start; /* ✅ allinea a sinistra */
  gap: 0.5rem;
  text-align: left;          /* ✅ testo a sinistra */
  padding: 0.2rem 0;
}

.log li span {
  min-width: 80px;           /* colonna tempo */
  color: #94a3b8;
  text-align: left;
}

.log li b {
  min-width: 100px;          /* colonna status */
  text-align: left;
}

.filters {
  display: flex;
  gap: 0.3rem;
  align-items: center;
}

.filters button {
  background: #020617;
  border: 1px solid #1e293b;
  color: #94a3b8;
  padding: 0.2rem 0.5rem;
  font-size: 0.75rem;
  cursor: pointer;
}

.filters button.active {
  background: #1e293b;
  color: #e5e7eb;
}

</style>
