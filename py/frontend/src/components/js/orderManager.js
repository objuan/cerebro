import {send_get} from '@/components/js/utils.js'; // Usa il percorso corretto

export async function order_breakout_no_slippage(symbol,op, qty, price){
    console.log("buy_breakout_no_slippage", symbol,op,qty, price)

    send_get("/order/buy_breakout_no_slippage", {
        "symbol" : symbol,
        "op": op,
        "qty": qty,
        "price" : price
    })
}

export async function order_bracket(symbol, timeframe,qty, price){
    console.log("bracket", symbol,timeframe,qty, price)

    send_get("/order/bracket", {
        "symbol" : symbol,
        "timeframe" : timeframe,
       // "qty": qty,
      //  "price" : price
    })
}
export async function order_single(symbol, timeframe,qty, price){
    console.log("single", symbol,timeframe,qty, price)

     send_get("/order/single", {
        "symbol" : symbol,
        "timeframe" : timeframe,
       // "qty": qty,
      //  "price" : price
    })
}

export async function order_existing_do_tp_sl(symbol, price, quantity, tp,sl){
    console.log("order_existing_do_tp_sl", symbol,price, quantity, tp,sl)

    send_get("/order/tp_sl", {
        "symbol" : symbol,
        "price" : price,
        "quantity": quantity,
        "stop_loss" : sl,
        "take_profit" : tp
        
    })
}


export async function order_tp_sl(symbol, timeframe, tp,sl){
    console.log("order_tp_sl", symbol,timeframe, tp,sl)

    send_get("/order/tp_sl/timeframe", {
        "symbol" : symbol,
        "timeframe" : timeframe,
       // "tp" : tp,
       // "sl" : sl
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

// SIMPLE BUY 
export async function order_limit(symbol, qty){
    console.log("order_limit", symbol,qty)

    send_get("/order/smart/limit", {
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


export async function sell_smart(symbol,perc){
    console.log("sell", symbol,perc)

    send_get("/order/sell/smart", {
        "symbol" : symbol,
        "perc": perc
    })
}