import {send_get} from '@/components/js/utils.js'; // Usa il percorso corretto

export async function order_bracket(symbol, timeframe,qty, price){
    console.log("bracket", symbol,timeframe,qty, price)

    send_get("/order/bracket", {
        "symbol" : symbol,
        "timeframe" : timeframe,
        "qty": qty,
        "price" : price
    })
}


export async function order_buy_at_level(symbol, qty, price){
    console.log("buy_at_level", symbol,qty, price)

    send_get("/order/buy_at_level", {
        "symbol" : symbol,
        "qty": qty,
        "price" : price
    })
}

export async function order_limit(symbol, qty){
    console.log("order_limit", symbol,qty)

    send_get("/order/limit", {
        "symbol" : symbol,
        "qty": qty,
    })
}

export async function clear_all_orders(symbol){
    console.log("clear_all_orders", symbol,)

    send_get("/order/clear_all", {
        "symbol" : symbol,
    })
}