import { ref } from "vue";

const contexts = new Map();

export function createChartContext(id, symbol, timeframe) {
    const ctx = {
        currentSymbol: ref(symbol),
        currentTimeframe: ref(timeframe),
    };
    contexts.set(id, ctx);
    return ctx;
}

export function useChartContext(id) {
    return contexts.get(id);
}