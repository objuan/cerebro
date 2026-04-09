//import {  send_post,generateGUID ,send_delete} from '@/components/js/utils.js'; // Usa il percorso corretto
import {  drawTextOnLine,drawLine,drawRect} from '@/components/js/chart_draw.js'; // Usa il percorso corretto
import {  SplitBox,PriceLine,Primitive,Handle} from '@/components/js/chart_primitives.js'; // Usa il percorso corretto

export  class TradeControl  extends Primitive{
constructor(painter){
    super(painter)
    this.isTradeMarker=true
}
 update(){
    super.update()
    this._update()
 }

_update(){
    
      const quantity = this.quantity()
      const price = this.buy_price()
      const tp = this.tp_price()
      const sl = this.sl_price()
      const profitPerc = 100 * ((tp- price) / price)
      const lossPerc = 100 * ((sl-price) / price)
      const rr = Math.abs((tp -price)  / (sl-price))
      const gain = (tp * quantity) - (quantity*price)
      const loss = (sl*quantity) - (quantity*price)

      this.price_txt=`Buy ${quantity} => <color:#000000>${(quantity*price).toFixed(1)}$</color> [ <color:#FFFF00>RR ${rr.toFixed(2)}</color>]`

      this.tp_txt=`Target  (${profitPerc.toFixed(1)}%) =><color:#000000>${(tp * quantity).toFixed(1)}$</color> Gain <color:#000000>${gain.toFixed(1)}$</color>`
      this.sl_txt=`Stop (${lossPerc.toFixed(1)}%) =><color:#000000>${(sl * quantity).toFixed(1)}$</color> Loss <color:#000000>${loss.toFixed(1)}$</color>`
      
      //this.risk_txt = `RR ${rr.toFixed(2)}`

      this.buy_price_txt = `${price.toFixed(2)}`
      this.tp_price_txt = `${tp.toFixed(2)}`
      this.sl_price_txt = `${sl.toFixed(2)}`
  }

}
// =============

export  class TradeRR  extends TradeControl{

   constructor(painter){
    super(painter)
    this.type = "trade-rr"
    this.p = new Handle(painter, this)
    this.isHover = false
    this.color = '#000000'
    this.trade_quantity_ref=painter.trade_quantity_ref
    this.trade_RR_ref=painter.trade_RR_ref
    this.trade_mode={}
    this.tradeMarkerData={}
   
  }
  setup(type,price_op){

     this.tradeMarkerData={type:type,price_op:price_op,
      quantity:this.trade_quantity_ref.value,
      price:0, take_profit:0, stop_loss:0
     }
    return true
  }
  buy_price_op(){
    return  this.tradeMarkerData["price_op"]
  }
  buy_type(){
    return  this.tradeMarkerData["type"]
  }
  quantity(){
    return  this.tradeMarkerData["quantity"]
  }
  buy_price(){
    return  this.tradeMarkerData["price"]
  }
  tp_price(){
    return  this.tradeMarkerData["take_profit"]
  }
  sl_price(){
    return  this.tradeMarkerData["stop_loss"]
  }
  clearLiveMarkerMode(){
     this.trade_mode = {"price": false, "tp" : false , "sl" : false}
  }
  setLiveMarkerMode(mode){
     this.trade_mode[mode] =true
  }
  props(){
    return [
      "color"
    ]
  }
  serialize(){
    return {
       ...super.serialize(),
        "p": this.p.serialize(),
        "color":  this.color,
        "tradeMarkerData" : this.tradeMarkerData
    }
  }
  fromSerial(data){
    console.log("fromSerial",data)
      super.fromSerial(data)
      this.p.fromSerial(data.p)
      this.color = data.color
      this.tradeMarkerData = data.tradeMarkerData
      this.update()
  }
  update(){
    this.tradeMarkerData["quantity"] = this.trade_quantity_ref.value
    super.update()
  }
  begin(p1){
    this.p.set(p1)
  }
  drag(p2){
    this.p.set(p2)
  }
  onEnd(){
    console.log("onEnd",this.p.val)
    
    const sl_perc = 0.25

    const openZone = this.painter.getOpenZone()
    this.tradeMarkerData["price"] = this.p.val.y
    const priceH = openZone.priceHeight()


    console.log("priceH",priceH)

    this.tradeMarkerData["stop_loss"] = this.p.val.y - priceH * sl_perc
    this.tradeMarkerData["take_profit"] = this.p.val.y + (priceH *sl_perc ) * this.trade_RR_ref.value
    this.update()
    super.onEnd()
     
  }

  draw(ctx){
    const buy_color = "#0000ff9d"
    const openZone = this.painter.getOpenZone()
    if (!openZone) return
    const closeTime = openZone.closeTimeUtc()

    const max_time_min = 45 
    const buy = this.painter.logicalToPixel ( {t:closeTime, y : this.buy_price() })
    const buy_right = this.painter.logicalToPixel ( {t:closeTime+max_time_min*60*1000, y : this.buy_price() })
    const tp = this.painter.logicalToPixel ( {t:closeTime, y : this.tp_price() })
    const sl = this.painter.logicalToPixel ( {t:closeTime, y : this.sl_price() })
   
    const t_l = {x : buy.x, y : tp.y}
    const m_l = {x : buy.x, y : buy_right.y}
    const m_r = {x : buy_right.x, y : buy_right.y}
    const b_r = {x : buy_right.x, y : sl.y}
    //const t_r = {x:b_r.x, y: t_l.y}
    //const b_l = {x:t_l.x, y: b_r.y}

      // =============

    const txt_right = this.painter.logicalToPixel ( {t:closeTime+max_time_min*2*60*1000, y : this.buy_price() })

    drawTextOnLine(ctx, {x:buy_right.x ,y :buy.y  }, { x: txt_right.x, y :buy.y} , this.price_txt, "white", -11, "left" , buy_color)
    drawTextOnLine(ctx, {x:buy_right.x ,y :tp.y  }, { x: txt_right.x, y :tp.y}, this.tp_txt, "white", 13, "left" , "#01a001be")
    drawTextOnLine(ctx, {x:buy_right.x ,y :sl.y  }, { x: txt_right.x, y :sl.y} , this.sl_txt, "white", -13, "left" , "#ff00008e")

    const pixel_band = this.painter.getPriceBand()

    const min_s = {x: pixel_band.min, y :t_l.y }
    const min_e=  {x: pixel_band.max, y :t_l.y }

    const max_s=  {x: pixel_band.min, y :b_r.y }
    const max_e=  {x: pixel_band.max, y :b_r.y }

    const mid_s = {x: pixel_band.min, y :m_l.y }
    const mid_e=  {x: pixel_band.max, y :m_l.y }

    const buy_price_txt = `${this.trade_mode["sl"] ? "🔥": ""}${this.tradeMarkerData["price"] ? "📌": ""} ${this.buy_price_txt}`
    const tp_price_txt = `${this.trade_mode["sl"] ? "🔥": ""}${this.tradeMarkerData["price"] ? "📌": ""} ${this.tp_price_txt}`
    const sl_price_txt = `${this.trade_mode["sl"] ? "🔥": ""}${this.tradeMarkerData["price"] ? "📌": ""} ${this.sl_price_txt}`


    drawTextOnLine(ctx, min_s, min_e , tp_price_txt, "white", 11, "right" , "green")
    drawTextOnLine(ctx, mid_s, mid_e , buy_price_txt, "white", -11, "right" , buy_color)
    drawTextOnLine(ctx, max_s, max_e , sl_price_txt, "white", -11, "right" , "red")

    //console.log("mM",min,max)
    drawRect(ctx,  t_l, m_r,"rgba(0,255,0,0.3)","rgba(0,255,0,0.05)")
    drawRect(ctx,  m_l, b_r,"rgba(255,0,0,0.3)","rgba(255,0,0,0.05)")

    drawLine(ctx,buy,buy_right,this.color, this.isHover)

    //if(this.isHover){
      this.p.draw(ctx)
    //}

  }

  pick(pos){
    //const a = this.painter.logicalToPixel (this.p.val)
    //const from = {x:0, y: a.y}
    //const to = {x:this.painter.getPriceBand().max, y: a.y}

    if(this.p.pick(pos)) return this.p
    if(this.isHover) return this

    return null
  }
}

// ===============================================

export  class  TradeBox  extends SplitBox{
   constructor(painter){
    super(painter)
    this.trade_quantity_ref=painter.trade_quantity_ref
    this.trade_RR_ref=painter.trade_RR_ref
    this.type = "trade-box"
    this.price_txt = ".."
    this.tp_txt = ".."
    this.sl_txt = ".."
    this.risk_txt = ".."
    this.tradeMarkerData={}
    this.trade_mode={}
    this.isTradeMarker = true
    this.clearLiveMarkerMode()
  }
  buy_price_op(){
    return ">"
  }
  buy_type(){
    return "bracket"
  }
  quantity(){
    return this.trade_quantity_ref.value
  }
  buy_price(){
    return this.center_left.val.y
  }
  tp_price(){
    return this.top_left.val.y
  }
  sl_price(){
    return this.bottom_right.val.y
  }
  clearLiveMarkerMode(){
     this.trade_mode = {"price": false, "tp" : false , "sl" : false}
  }
  setLiveMarkerMode(mode){
     this.trade_mode[mode] =true
  }
  onEnd(){
     //console.log("end")
     this.save()
     
     this.painter.tradeBoxHandler.change(this);
  }

  compute_middleY(){
    // 1 -> 2
    // 2 -> 3
    const upPerc = this.trade_RR_ref.value;

    const p1 = this.top_left
    const p2 = this.bottom_right
    const y_min = Math.min(p1.val.y, p2.val.y)
    const y_max = Math.max(p1.val.y, p2.val.y)

    return y_min+ (y_max-y_min)/ (upPerc+1)
  }
  update(){

      super.update()
      const quantity = this.trade_quantity_ref.value;
      const price = this.center_left.val.y
      const tp = this.top_left.val.y;
      const sl = this.bottom_right.val.y;
      const profitPerc = 100 * ((tp- price) / price)
      const lossPerc = 100 * ((sl-price) / price)
      const rr = Math.abs((tp -price)  / (sl-price))
      const gain = (tp * quantity) - (quantity*price)
      const loss = (sl*quantity) - (quantity*price)

      this.price_txt=`Buy ${quantity} => <color:#000000>${(quantity*price).toFixed(1)}$</color> [ <color:#FFFF00>RR ${rr.toFixed(2)}</color>]`

      this.tp_txt=`Target  (${profitPerc.toFixed(1)}%) =><color:#000000>${(tp * quantity).toFixed(1)}$</color> Gain <color:#000000>${gain.toFixed(1)}$</color>`
      this.sl_txt=`Stop (${lossPerc.toFixed(1)}%) =><color:#000000>${(sl * quantity).toFixed(1)}$</color> Loss <color:#000000>${loss.toFixed(1)}$</color>`
      

      //this.risk_txt = `RR ${rr.toFixed(2)}`

      this.buy_price_txt = `${price.toFixed(2)}`
      this.tp_price_txt = `${tp.toFixed(2)}`
      this.sl_price_txt = `${sl.toFixed(2)}`
  }

  draw(ctx){
    const t_l = this.painter.logicalToPixel (this.top_left.val)
    const m_l = this.painter.logicalToPixel (this.center_left.val)
    const m_r = this.painter.logicalToPixel (this.center_right.val)
    const b_r = this.painter.logicalToPixel (this.bottom_right.val)

    const t_r = {x:b_r.x, y: t_l.y}
    const b_l = {x:t_l.x, y: b_r.y}

    const buy_color = "#5f5fff"
    
    drawTextOnLine(ctx, m_l, m_r , this.price_txt, "white", -11, "center" , buy_color)
    //drawTextOnLine(ctx, m_l, m_r , this.risk_txt, "white", -31, "center" , buy_color)

    drawTextOnLine(ctx, t_l, t_r , this.tp_txt, "white", 13, "center" , "green")
    drawTextOnLine(ctx, b_l, b_r , this.sl_txt, "white", -13, "center" , "red")

    let pixel_band = this.painter.getPriceBand()
    //pixel_band.max = 1042

    const min_s = {x: pixel_band.min, y :t_l.y }
    const min_e=  {x: pixel_band.max, y :t_l.y }

    const max_s=  {x: pixel_band.min, y :b_r.y }
    const max_e=  {x: pixel_band.max, y :b_r.y }

    const mid_s = {x: pixel_band.min, y :m_l.y }
    const mid_e=  {x: pixel_band.max, y :m_l.y }

    //console.log("mM",min,max)
    drawRect(ctx, min_s, max_e, "rgba(187, 187, 187, 0.1)", "rgba(187, 187, 187, 0.0)")

    const buy_price_txt = `${this.trade_mode["sl"] ? "🔥": ""}${this.tradeMarkerData["price"] ? "📌": ""} ${this.buy_price_txt}`
    const tp_price_txt = `${this.trade_mode["sl"] ? "🔥": ""}${this.tradeMarkerData["price"] ? "📌": ""} ${this.tp_price_txt}`
    const sl_price_txt = `${this.trade_mode["sl"] ? "🔥": ""}${this.tradeMarkerData["price"] ? "📌": ""} ${this.sl_price_txt}`

    drawTextOnLine(ctx, min_s, min_e , tp_price_txt, "white", 11, "right" , "green")
    drawTextOnLine(ctx, mid_s, mid_e , buy_price_txt, "white", -11, "right" , buy_color)
    drawTextOnLine(ctx, max_s, max_e , sl_price_txt, "white", -11, "right" , "red")

      //  console.log(t_l, m_l,m_r,b_r  ) 
    drawRect(ctx,  t_l, m_r,"rgba(0,255,0,0.3)","rgba(0,255,0,0.05)")
    drawRect(ctx,  m_l, b_r,"rgba(255,0,0,0.3)","rgba(255,0,0,0.05)")

    drawLine(ctx, t_l,t_r , "green",this.isHover, 1)
    drawLine(ctx, m_l,m_r , "blue",this.isHover, 1)
    drawLine(ctx, b_l,b_r , "red",this.isHover, 1)

    if(this.isHover){
      this.top_left.draw(ctx)
      this.bottom_right.draw(ctx)
      this.center_left.draw(ctx)
      this.center_right.draw(ctx)
      this.bottom_left.draw(ctx)
    }

   if (this.hasAlarm()){
      drawTextOnLine(ctx,mid_s,mid_e,"🔔","white",10,"center")
    }


   }
}

// ==========

class _TradeSingle extends PriceLine{
  constructor(painter){
    super(painter)
    this.trade_quantity_ref=painter.trade_quantity_ref
    this.tradeMarkerData={}
    this.clearLiveMarkerMode()
     this.isTradeMarker = true
   // console.log("TradeSingle")
  }
    onEnd(){
     this.save()
     this.painter.tradeBoxHandler.change(this);
  }

   clearLiveMarkerMode(){
     this.trade_live_mode = {"price": false, "tp" : false , "sl" : false}
  }
  setLiveMarkerMode(mode){
     this.trade_live_mode[mode] =true
  }

   quantity(){
    return this.trade_quantity_ref.value
  }
  buy_type(){
    return "single"
  }
   tp_price(){
    return 0
  }
  sl_price(){
    return 0
  }
  getText(){
   // console.log("getText",this.trade_live_mode,  this.tradeMarkerData)
    return `${this.trade_live_mode["price"] ? "🔥": ""} ${this.tradeMarkerData["price"] ? "📌": ""} ${this.buy_price_op()} ${this.p.val.y.toFixed(2)}`
  }

  buy_price(){
    return this.p.val.y
  }
  buy_price_op(){
    return ""
  }
}

export class BuyAbove extends _TradeSingle{
  constructor(painter){
    super(painter)
    this.type = "buy-above"
    this.color ="#2f9934"
  }
  buy_price_op(){
    return ">"
  }
}

export class BuyBelow extends _TradeSingle{
  constructor(painter){
    super(painter)
    this.type = "buy-below"
    this.color ="#ac3709"
  }
  buy_price_op(){
    return "<"
  }
}


export  class TradeSL_TP  extends TradeRR{

   constructor(painter){
    super(painter)
      this.type = "trade-tp_sl"
       this.trade_mode = {"price": false, "tp" : true , "sl" : true}
    }
  
    onEnd(){
     this.save()
    // this.painter.tradeBoxHandler.change(this);
  }

    update(){
   this._update()
  }

  draw(ctx){
   
   // const buy_color = "#0000ff9d"
    const openZone = this.painter.getOpenZone()
    if (!openZone) return
    const closeTime = openZone.closeTimeUtc()

    //console.log("this.tradeMarkerData",this.tradeMarkerData)

    const max_time_min = 45 
    const buy = this.painter.logicalToPixel ( {t:closeTime, y : this.buy_price() })
    const buy_right = this.painter.logicalToPixel ( {t:closeTime+max_time_min*60*1000, y : this.buy_price() })
    const tp = this.painter.logicalToPixel ( {t:closeTime, y : this.tp_price() })
    const sl = this.painter.logicalToPixel ( {t:closeTime, y : this.sl_price() })
   
    const t_l = {x : buy.x, y : tp.y}
   // const m_l = {x : buy.x, y : buy_right.y}
   // const m_r = {x : buy_right.x, y : buy_right.y}
    const b_r = {x : buy_right.x, y : sl.y}

    const pixel_band = this.painter.getPriceBand()

    const min_s = {x: pixel_band.min, y :t_l.y }
    const min_e=  {x: pixel_band.max, y :t_l.y }

    const max_s=  {x: pixel_band.min, y :b_r.y }
    const max_e=  {x: pixel_band.max, y :b_r.y }

   // const mid_s = {x: pixel_band.min, y :m_l.y }
  //  const mid_e=  {x: pixel_band.max, y :m_l.y }

    //const buy_price_txt = `${this.trade_mode["sl"] ? "🔥": ""}${this.tradeMarkerData["price"] ? "📌": ""} ${this.buy_price_txt}`
    const tp_price_txt = `${this.trade_mode["sl"] ? "🔥": ""}${this.tradeMarkerData["price"] ? "📌": ""} ${this.tp_price_txt}`
    const sl_price_txt = `${this.trade_mode["sl"] ? "🔥": ""}${this.tradeMarkerData["price"] ? "📌": ""} ${this.sl_price_txt}`

    drawTextOnLine(ctx, min_s, min_e , tp_price_txt, "white", 11, "right" , "green")
    drawLine(ctx, {x:0, y :min_e.y },min_e, "green" , false, 1, "dotted")

    //drawTextOnLine(ctx, mid_s, mid_e , buy_price_txt, "white", -11, "right" , buy_color)
    drawTextOnLine(ctx, max_s, max_e , sl_price_txt, "white", -11, "right" , "red")
    drawLine(ctx, {x:0, y :max_e.y },max_e, "red" , false, 1, "dotted")


  }
}