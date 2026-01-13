import {send_mulo__get} from '@/components/js/utils.js'; // Usa il percorso corretto

export async function order_limit(symbol, qty, price){
    console.log("order_limit", symbol,qty, price)

    send_mulo__get("/order/limit", {
        "symbol" : symbol,
        "qty": qty,
        "price" : price
    })
}