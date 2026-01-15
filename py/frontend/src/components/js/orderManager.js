import {send_mulo_get} from '@/components/js/utils.js'; // Usa il percorso corretto

export async function order_limit(symbol, qty, price){
    console.log("order_limit", symbol,qty, price)

    send_mulo_get("/order/limit", {
        "symbol" : symbol,
        "qty": qty,
        "price" : price
    })
}

export async function clear_all_orders(symbol){
    console.log("clear_all_orders", symbol,)

    send_mulo_get("/order/clear_all", {
        "symbol" : symbol,
    })
}