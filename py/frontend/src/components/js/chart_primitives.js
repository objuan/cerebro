import {  send_post,generateGUID ,send_delete} from '@/components/js/utils.js'; // Usa il percorso corretto
import {  drawHandle,hitHandle,drawTextOnLine,hitLine,handleSize,drawLine,drawRect} from '@/components/js/chart_draw.js'; // Usa il percorso corretto



class Primitive {
  constructor(painter){
       this.painter=painter
       this.guid = generateGUID()
       this.virtual=false
       this.style ="solid"
       this.alarms=[]
  }
  end(){
     this.onEnd()
  }
  // type : "above" : "below"
  addAlarm(source,type){
      this.alarms.push({source : source, type: type})
  }
  hasAlarm(){
    return this.alarms.length>0
  }
  onEnd(){

     this.save()
  }
  update(){}
  edit(){
      return false
  }
  isDraggable(){
    return false
  }
  filter(p, new_pos){
    return new_pos
  }
  delete(){
    console.log("delete",this)
     send_delete("/api/chart/painter/delete",
      {
          guid: this.guid
        });
    this.painter.onDelete(this.guid)
  }
  onChange(){
  }
  save(){
      if (this.virtual)
        return
      console.log("save", this)
      let s = this.painter.context.currentSymbol.value
      if (!s) s = this.painter.context.currentSymbol
      let tf = this.painter.context.currentTimeframe.value
      if (!tf) tf = this.painter.context.currentTimeframe
      const data = this.serialize()
       // console.log("serial", data,this.painter.context.currentSymbol)
      data.type = this.type
      data.alarms = this.alarms
      send_post("/api/chart/painter/save",
      {
          symbol: s,
          timeframe:tf,
          guid: this.guid,
          type: this.type,
          data:  data
        });
  }
  serialize(){
  
  }
  fromSerial(data){
      this.alarms = data.alarms
  }
}

// =======================================

export class Handle  extends Primitive{

  constructor(painter, parent){
    super(painter)
    this.type = "handle"
    this.parent = parent
    this.val = null
    this.isHover = false
  }

  set(p){
    this.val = p
  }
  end(){
     this.parent.end()
  }

  edit(){
      return false
  }
  isDraggable(){
    return true
  }
  draw(ctx){
    const a = this.painter.chartToPixel(this.val)
    drawHandle(ctx, a, this.isHover)
  }

  drag(pos){
    pos = this.parent.filter(this, pos)
    this.val = pos
    this.parent.onChange(this)
  }

  pick(pos){
    const a = this.painter.chartToPixel(this.val)
    this.isHover = hitHandle(pos, a)
    return this.isHover ? this : null
  }
  serialize(){
    return {"val" : this.val,"time": this.painter.chartToTime(this.val)}
  }
  fromSerial(ser){
    
    this.val = ser.val
  }
}
// ============

export class Point  extends Primitive{
  constructor(painter, parent){
    super(painter)
    this.type = "point"
    this.parent = parent
    this.val = null
    this.isHover = false
  }
  set(p){
    this.val = p
  }
}

// =============


class Text  extends Primitive{
   constructor(painter,parent){
      super(painter)
      this.parent=parent
      this.value=null;
      this.align = "center"
      this.color = "white"
      this.bgColor = null
   }
   set(p1,p2){
      this.p1=p1
      this.p2=p2
   }
   props(){
    return [
      "color","bgColor","value","align"
    ]
  }
   pick(pos){
      if(!this.value) return null

      // punti linea
      const a = this.painter.chartToPixel(this.p1.val)
      const b = this.painter.chartToPixel(this.p2.val)

      // midpoint
      const midX = (a.x + b.x) / 2
      const midY = (a.y + b.y) / 2

      // angolo linea
      const angle = Math.atan2(b.y - a.y, b.x - a.x)

      // trasformazione inversa del mouse
      const dx = pos.x - midX
      const dy = pos.y - midY

      const cos = Math.cos(-angle)
      const sin = Math.sin(-angle)

      const lx = dx * cos - dy * sin
      const ly = dx * sin + dy * cos

      // misura testo
      const ctx = this.painter.ctx
      const metrics = ctx.measureText(this.value)

      const width = metrics.width
      const height =
        (metrics.actualBoundingBoxAscent || 8) +
        (metrics.actualBoundingBoxDescent || 4)

      const offset = 10
      const y = -offset

      // bounding box locale
      let x1, x2
      if(this.align === "center"){
        x1 = -width/2
        x2 =  width/2
      }else if(this.align === "left"){
        x1 = 0
        x2 = width
      }else{
        x1 = -width
        x2 = 0
      }

      const y1 = y - height/2
      const y2 = y + height/2

      // hit test
      if(lx >= x1 && lx <= x2 && ly >= y1 && ly <= y2)
        return this

      return null
    }
   draw(ctx, parentIsHover){
    if (this.value || parentIsHover)
    {
      const a = this.painter.chartToPixel(this.p1.val)
      const b = this.painter.chartToPixel(this.p2.val)
      if (parentIsHover & !this.value)
      {
        drawTextOnLine(ctx,a,b,"click to add ..", "gray", 10, this.align )
      }
      else
        drawTextOnLine(ctx,a,b,this.value,this.color, 10, this.align,this.bgColor )
    }
   }
}

// =============
export  class Line  extends Primitive{

  constructor(painter){
    super(painter)
    this.type = "line"
    this.p1 = new Handle(painter, this)
    this.p2 = new Handle(painter, this)
    this.isHover = false

    this.color = "white"
    this.text = new Text(painter,this)
    this.text.set(this.p1, this.p2)
    //this.text.value = "pippo"
  }
  props(){
    return [
      "color","text","alarms"
    ]
  }
  serialize(){
    return {
        ...super.serialize(),
        "p1": this.p1.serialize(),
        "p2":   this.p2.serialize(),
        "color":  this.color,
    }
  }
  fromSerial(data){
 //   console.log("fromSerial",data)
      super.fromSerial(data)
      this.p1.fromSerial(data.p1)
      this.p2.fromSerial(data.p2)
      this.color = data.color
  }
  begin(p1){
    this.p1.set(p1)
    this.p2.set(p1)
  }

  drag(p2){
    p2 = this.filter(this.p2, p2)
    this.p2.set(p2)
  }


  filter(p, new_pos){
    return new_pos
  }

  draw(ctx){
    const a = this.painter.chartToPixel(this.p1.val)
    const b = this.painter.chartToPixel(this.p2.val)

   // console.log(a,b,this.color)
    drawLine(ctx, a, b,this.color, this.isHover)
    this.text.draw(ctx,this.isHover)
    if(this.isHover){
      this.p1.draw(ctx)
      this.p2.draw(ctx)
    }
    if (this.hasAlarm()){
      drawTextOnLine(ctx,a,b,"🔔","white",10,"center")
    }
  }

  pick(pos){
    const a = this.painter.chartToPixel(this.p1.val)
    const b = this.painter.chartToPixel(this.p2.val)

    this.isHover = false

    if(hitLine(pos, a, b))
      this.isHover = true

    if(this.p1.pick(pos)) return this.p1
    if(this.p2.pick(pos)) return this.p2
    if(this.isHover) return this

    return null
  }
}

// =============

export  class PriceLine  extends Primitive{

   constructor(painter){
    super(painter)
    this.type = "price-line"
    this.p = new Handle(painter, this)
    this.isHover = false
    this.color = '#ea00ff'
  }
  props(){
    return [
      "color","alarms"
    ]
  }
  serialize(){
    return {
       ...super.serialize(),
        "p": this.p.serialize(),
        "color":  this.color,
    }
  }
  fromSerial(data){
   // console.log("fromSerial",data)
      super.fromSerial(data)
      this.p.fromSerial(data.p)
      this.color = data.color
  }
  begin(p1){
    this.p.set(p1)
  }

  drag(p2){
    this.p.set(p2)
  }

  draw(ctx){

    const a = this.painter.chartToPixel(this.p.val)
    const from = {x:0, y: a.y}
    const to = {x:this.painter.getPriceBand().max, y: a.y}
    drawLine(ctx,from,to,this.color, this.isHover)

    drawTextOnLine(ctx, from, to , `${this.p.val.y.toFixed(2)}`,
    "black", 6, "right" , this.color, 1,"13px Arial")

    if(this.isHover){
      this.p.draw(ctx)
    }

     if (this.hasAlarm()){
      drawTextOnLine(ctx,from,to,"🔔","white",10,"center")
    }
  }

  pick(pos){
    const a = this.painter.chartToPixel(this.p.val)
    const from = {x:0, y: a.y}
    const to = {x:this.painter.getPriceBand().max, y: a.y}

    this.isHover = false

    if(hitLine(pos, from,to))
      this.isHover = true

    if(this.p.pick(pos)) return this.p
    if(this.isHover) return this

    return null
  }
}
/*
export  class AlarmLine  extends PriceLine{
    constructor(painter){
    super(painter)
    this.type = "alarm-line"
  }
}
  */

// ============

export  class Box  extends Primitive{

  constructor(painter){
    super(painter)
    this.type = "box"
    this.top_left = new Handle(painter, this)
    this.top_right = new Point(painter, this)
    this.bottom_left = new Point(painter, this)
    this.bottom_right = new Handle(painter, this)

    this.isHover = false
    this.color ='rgba(255,255,255,0.1)'
    this.text = new Text(painter,this)
    this.text.set(this.top_left, this.top_right)
  }
  props(){
    return [
      "color","text"
    ]
  }
 serialize(){
    return {
        "top_left": this.top_left.val,
        "bottom_right":   this.bottom_right.val,
        "color":  this.color,
    }
  }
  fromSerial(data){
   // console.log("fromSerial",data)
      super.fromSerial(data)
      this.top_left.val = data.top_left
      this.bottom_right.val = data.bottom_right
      this.color = data.color
  }
  edit(){
      window.dispatchEvent(new CustomEvent("edit-object", {
        detail: this
      }))
      return true;
  }
  
  begin(p1){
    this.top_left.set(p1)
    this.bottom_right.set(p1)
  }

  drag(p2){
    this.bottom_right.set(p2)
    this.top_right.val = {x:this.bottom_right.val.x, y : this.top_left.val.y }
    this.bottom_left.val = {x:this.top_left.val.x, y : this.bottom_right.val.y }
  }

  draw(ctx){
    const a = this.painter.chartToPixel(this.top_left.val)
    const b = this.painter.chartToPixel(this.bottom_right.val)

    drawRect(ctx, a, b,"white",this.color,  this.isHover)

    if(this.isHover){
      this.top_left.draw(ctx)
      this.bottom_right.draw(ctx)
    }
  }

  pick(pos){
    this.isHover = false

    // rettangolo in pixel
    const a = this.painter.chartToPixel(this.top_left.val)
    const b = this.painter.chartToPixel(this.bottom_right.val)

    const x1 = Math.min(a.x, b.x)
    const x2 = Math.max(a.x, b.x)
    const y1 = Math.min(a.y, b.y)
    const y2 = Math.max(a.y, b.y)

    if(pos.x >= x1-handleSize && pos.x <= x2+handleSize 
      && pos.y >= y1-handleSize && pos.y <= y2+handleSize){
      this.isHover = true
    }

    if(this.top_left.pick(pos)) return this.top_left
    if(this.bottom_right.pick(pos)) return this.bottom_right

    return this.isHover ? this : null
  }
}

// ======

export  class HLine extends Line {

  constructor(painter){
    super(painter)
    this.type = "hline"
  }

  filter(p, new_pos){
    const other = (this.p1 === p) ? this.p2 : this.p1
    new_pos.y = other.val.y
    return new_pos
  }
}

// ========================


export  class VLine  extends PriceLine{

   constructor(painter){
    super(painter)
    this.type = "vline"
    this.color = '#1268d8'
  }
  draw(ctx){
   
    const a = this.painter.chartToPixel(this.p.val)
    const from = {x:a.x, y: 0}
    const to = {x:a.x,y:this.painter.geHeight()}

   //  console.log("draw",from,to)

    drawLine(ctx,from,to,this.color, this.isHover, 1, this.style)

    if(this.isHover){
      this.p.draw(ctx)
    }
  }

  pick(pos){
    const a = this.painter.chartToPixel(this.p.val)
    const from = {x:a.x, y: 0}
    const to = {x:a.x,y:this.painter.geHeight()}

    this.isHover = false

    if(hitLine(pos, from,to))
      this.isHover = true

    if(this.p.pick(pos)) return this.p
    if(this.isHover) return this

    return null
  }
}

// ======================================================

export  class SplitBox  extends Box{
   constructor(painter){
    super(painter)
    this.type = "split-box"
    this.center_left = new Handle(painter, this)
    this.center_right = new Point(painter, this)
  }
   props(){
    return [
      "color","text","alarms"

    ]
  }
   serialize(){
     let ser = super.serialize()
     ser.center_left = this.center_left.val
      return ser;
  }
  fromSerial(data){
      super.fromSerial(data)
      this.center_left.val = data.center_left
      this.update()
  }
  drag(p2){
    super.drag(p2)
    this.center_left.set({ x: this.top_left.val.x , y:this.compute_middleY()} )
    this.update()
  }
  onChange(handle){
    //console.log("onChange",handle )
    if (handle == this.top_left){
        this.center_left.set( 
          { x: this.top_left.val.x ,
           y:this.center_left.val.y} )
    }
     if (handle == this.center_left){
        this.top_left.set( 
          { x: this.center_left.val.x ,
           y:this.top_left.val.y} )
    }
    this.update()
  }
  compute_middleY(){
    const p1 = this.top_left
    const p2 = this.bottom_right
    const y_min = Math.min(p1.val.y, p2.val.y)
    const y_max = Math.max(p1.val.y, p2.val.y)

    return y_min+ (y_max-y_min)/2
  }
  update(){
      this.center_right.set(
        { x: this.bottom_right.val.x , y:this.center_left.val.y} )     
  }
  pick(pos){
    if(this.center_left.pick(pos)) return this.center_left

    return super.pick(pos)
  }
   draw(ctx){
      super.draw(ctx)
      if (!this.center_left.val)
        return
      const p1 = this.top_left
      const p2 = this.bottom_right
      const y_min = Math.min(p1.val.y, p2.val.y)
      const y_max = Math.max(p1.val.y, p2.val.y)

      const m_l = this.painter.chartToPixel(this.center_left.val)
      const m_r = this.painter.chartToPixel(this.center_right.val)

      const delta = y_max- y_min;
      const p =   100 * ((this.center_left.val.y - y_min) / delta)

      drawTextOnLine(ctx, m_l, m_r ,`${p.toFixed(1)}%`, "white", -11, "right" , this.color)
      drawLine(ctx,m_l,m_r,"white",this.isHover )

     if(this.isHover){
      this.center_left.draw(ctx)
    }
      if (this.hasAlarm()){
      drawTextOnLine(ctx,m_l,m_r,"🔔","white",10,"center")
    }

   }
}

/// ======================================

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
    this.clearMarkerMode()
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
  clearMarkerMode(){
     this.trade_mode = {"price": false, "tp" : false , "sl" : false}
  }
  setMarkerMode(mode){
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
    const t_l = this.painter.chartToPixel(this.top_left.val)
    const m_l = this.painter.chartToPixel(this.center_left.val)
    const m_r = this.painter.chartToPixel(this.center_right.val)
    const b_r = this.painter.chartToPixel(this.bottom_right.val)

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
    drawRect(ctx, min_s, max_e, "rgba(187, 187, 187, 0.1)", "rgba(187, 187, 187, 0.1)")

    const buy_price_txt = `${this.trade_mode["price"] ? "🏁": ""} ${this.buy_price_txt}`
    const tp_price_txt = `${this.trade_mode["tp"] ? "🏁": ""} ${this.tp_price_txt}`
    const sl_price_txt = `${this.trade_mode["sl"] ? "🏁": ""} ${this.sl_price_txt}`

    drawTextOnLine(ctx, min_s, min_e , tp_price_txt, "white", 11, "right" , "green")
    drawTextOnLine(ctx, mid_s, mid_e , buy_price_txt, "white", -11, "right" , buy_color)
    drawTextOnLine(ctx, max_s, max_e , sl_price_txt, "white", -11, "right" , "red")

      //  console.log(t_l, m_l,m_r,b_r  ) 
    drawRect(ctx,  t_l, m_r,"rgba(0,255,0,0.3)","rgba(0,255,0,0.1)")
    drawRect(ctx,  m_l, b_r,"rgba(255,0,0,0.3)","rgba(255,0,0,0.1)")

    drawLine(ctx, t_l,t_r , "green",this.isHover, 2)
    drawLine(ctx, m_l,m_r , "blue",this.isHover, 2)
    drawLine(ctx, b_l,b_r , "red",this.isHover, 2)

    if(this.isHover){
      this.top_left.draw(ctx)
      this.bottom_right.draw(ctx)
      this.center_left.draw(ctx)
    }

   if (this.hasAlarm()){
      drawTextOnLine(ctx,mid_s,mid_e,"🔔","white",10,"center")
    }


   }
}

// ======================================================


