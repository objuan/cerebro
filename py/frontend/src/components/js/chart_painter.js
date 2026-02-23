import { send_get, send_post,generateGUID } from '@/components/js/utils.js'; // Usa il percorso corretto

const handleSize=6

function drawTextOnLine(
  ctx,
  a,
  b,
  text,
  color = "white",
  offset = 10,
  anchor = "center",   // ⭐ left | right | center
  bgColor = null,
  padding = 4,
  font = "14px Arial"
){
  const angle = Math.atan2(b.y - a.y, b.x - a.x);

  // ⭐ origine
  let origin;
  if(anchor === "left") origin = a;
  else if(anchor === "right") origin = b;
  else origin = { x:(a.x+b.x)/2, y:(a.y+b.y)/2 };

  ctx.save();
  ctx.translate(origin.x, origin.y);
  ctx.rotate(angle);

  ctx.font = font;
  ctx.textBaseline = "middle";

  const metrics = ctx.measureText(text);
  const width = metrics.width;
  const height =
    (metrics.actualBoundingBoxAscent || 8) +
    (metrics.actualBoundingBoxDescent || 4);

  const y = -offset;

  let textX;
  let rectX;

  // ⭐ logica anchor
  if(anchor === "left"){
    textX = padding;
    rectX = textX - padding;
    ctx.textAlign = "left";
  }
  else if(anchor === "right"){
    textX = -padding;
    rectX = -width - padding;
    ctx.textAlign = "right";
  }
  else{
    textX = 0;
    rectX = -width/2 - padding;
    ctx.textAlign = "center";
  }

  if(bgColor){
    ctx.fillStyle = bgColor;
    ctx.fillRect(
      rectX,
      y - height/2 - padding,
      width + padding*2,
      height + padding*2
    );
  }

  ctx.fillStyle = color;
  ctx.fillText(text, textX, y);

  ctx.restore();
}

function  drawLine(ctx, a,b,color, hover=false){
      ctx.beginPath()
      ctx.moveTo(a.x,a.y)
      ctx.lineTo(b.x,b.y)
      ctx.strokeStyle = hover ? 'yellow' : color
      ctx.lineWidth = hover ? 2 : 1
      ctx.stroke()
}
function drawRect(ctx, a, b,color, fillColor,hover=false){
    const x = Math.min(a.x, b.x)
    const y = Math.min(a.y, b.y)
    const w = Math.abs(b.x - a.x)
    const h = Math.abs(b.y - a.y)

    ctx.beginPath()
    ctx.rect(x, y, w, h)

    // riempimento
    ctx.fillStyle = fillColor
    ctx.fill()

    // bordo
    ctx.strokeStyle = hover ? 'yellow' : color
    ctx.lineWidth = hover ? 2 : 1
    ctx.stroke()
}

function drawHandle(ctx,p,hover=false){
      ctx.beginPath()
      ctx.arc(p.x, p.y, handleSize, 0, Math.PI*2)
      ctx.fillStyle = hover ? 'green' : 'yellow'
      ctx.fill()
  }

function hitLine(mouse, a, b, tolerance = 6){
      // lunghezza segmento
      const dx = b.x - a.x
      const dy = b.y - a.y

      const lenSq = dx*dx + dy*dy
      if(lenSq === 0) return false

      // proiezione del mouse sul segmento
      let t = ((mouse.x - a.x)*dx + (mouse.y - a.y)*dy) / lenSq

    
      // clamp sul segmento
      t = Math.max(0, Math.min(1, t))

      // punto più vicino sulla linea
      const px = a.x + t*dx
      const py = a.y + t*dy

      // distanza mouse → linea
      const dist = Math.hypot(mouse.x - px, mouse.y - py)

      return dist <= tolerance
    }

  function hitHandle(mouse,p){
      return Math.hypot(mouse.x-p.x, mouse.y-p.y) <= handleSize+2
    }

// ======================================================

class Primitive {
  constructor(painter){
       this.painter=painter
       this.guid = generateGUID()
  }
  end(){
     this.save()
  }

  edit(){
      return false
  }
  filter(p, new_pos){
    return new_pos
  }
  delete(){
    console.log("delete",this)
  }
  onChange(){
  }
  save(){
      console.log("save", this)
      let s = this.painter.context.currentSymbol.value
      if (!s) s = this.painter.context.currentSymbol
      let tf = this.painter.context.currentTimeframe.value
      if (!tf) tf = this.painter.context.currentTimeframe
      const data = this.serialize()
       // console.log("serial", data,this.painter.context.currentSymbol)
      data.type = this.type
      send_post("/api/chart/save",
      {
          symbol: s,
          timeframe:tf,
          guid: this.guid,
          type: this.type,
          data:  data
        });
  }
  serialize(){
    return {}
  }
  fromSerial(){
    
  }
}

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
     this.parent.save()
  }

  edit(){
      return false
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
class Line  extends Primitive{

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
      "color","text"
    ]
  }
  serialize(){
    return {
        "p1": this.p1.val,
        "p2":   this.p2.val,
        "color":  this.property,
    }
  }
  fromSerial(data){
    console.log("fromSerial",data)
      this.p1.val = data.p1
      this.p2.val = data.p2
  }
  begin(p1){
    this.p1.set(p1)
    this.p2.set(p1)
  }

  drag(p2){
    p2 = this.filter(this.p2, p2)
    this.p2.set(p2)
  }

  /*
  edit(){
      window.dispatchEvent(new CustomEvent("edit-object", {
        detail: this
      }))
      return true;
  }
      */
  

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

// ============

class Box  extends Primitive{

  constructor(painter){
    super(painter)
    this.type = "box"
    this.top_left = new Handle(painter, this)
    this.top_right = new Point(painter, this)
    this.bottom_left = new Point(painter, this)
    this.bottom_right = new Handle(painter, this)

    this.isHover = false
    this.color ='rgba(255,255,255,0.2)'
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
    console.log("fromSerial",data)
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

class HLine extends Line {

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


// ======================================================

class TradeBox  extends Box{
   constructor(painter){
    super(painter)
    this.type = "trade-box"
    this.center_left = new Handle(painter, this)
    this.center_right = new Point(painter, this)
    this.price_txt = ".."
    this.tp_txt = ".."
    this.sl_txt = ".."
    this.risk_txt = ".."
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
    this.center_left.set({ x: this.top_left.val.x , y:this.middleY()} )
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
  middleY(){
    const p1 = this.top_left
    const p2 = this.bottom_right
    const y_min = Math.min(p1.val.y, p2.val.y)
    const y_max = Math.max(p1.val.y, p2.val.y)

    return y_min+ (y_max-y_min)/2
  }
  update(){
      this.center_right.set(
        { x: this.bottom_right.val.x , y:this.center_left.val.y} )
      const quantity = 100;
      const price = this.center_left.val.y
      const tp = this.top_left.val.y;
      const sl = this.bottom_right.val.y;
      const profit = 100 * ((tp- price) / price)
      const loss = 100 * ((sl-price) / price)
      const rr = Math.abs((tp -price)  / (sl-price))

      this.price_txt=`Buy ${price.toFixed(4)} (${quantity}) => ${(quantity*price).toFixed(1)}$`

      this.tp_txt=`Target ${tp.toFixed(4)} (${profit.toFixed(1)}%) ${(tp * quantity).toFixed(4)} $`
      this.sl_txt=`Stop ${sl.toFixed(4)} (${loss.toFixed(1)}%) ${(sl * quantity).toFixed(4)} $`
      

      this.risk_txt = `RR ${rr.toFixed(2)}`

      this.buy_price_txt = `${price.toFixed(2)}`
      this.tp_price_txt = `${tp.toFixed(2)}`
      this.sl_price_txt = `${sl.toFixed(2)}`
     
  }
  pick(pos){
    if(this.center_left.pick(pos)) return this.center_left

    return super.pick(pos)
  }
   draw(ctx){
    const t_l = this.painter.chartToPixel(this.top_left.val)
    const m_l = this.painter.chartToPixel(this.center_left.val)
    const m_r = this.painter.chartToPixel(this.center_right.val)
    const b_r = this.painter.chartToPixel(this.bottom_right.val)

    const t_r = {x:b_r.x, y: t_l.y}
    const b_l = {x:t_l.x, y: b_r.y}


    //  console.log(t_l, m_l,m_r,b_r  ) 
    drawRect(ctx,  t_l, m_r,"white","rgba(0,255,0,0.1)")
    drawRect(ctx,  m_l, b_r,"white","rgba(255,0,0,0.1)")

    if(this.isHover){
      this.top_left.draw(ctx)
      this.bottom_right.draw(ctx)
      this.center_left.draw(ctx)
    }

    
    drawTextOnLine(ctx, m_l, m_r , this.price_txt, "white", -11, "center" , "blue")
    drawTextOnLine(ctx, m_l, m_r , this.risk_txt, "white", -31, "center" , "blue")

    drawTextOnLine(ctx, t_l, t_r , this.tp_txt, "white", 13, "center" , "green")
    drawTextOnLine(ctx, b_l, b_r , this.sl_txt, "white", -13, "center" , "red")

    const pixel_band = this.painter.getPriceBand()

    const min = {x: pixel_band.min-100, y :t_l.y }
    const min_t=  {x: pixel_band.min, y :t_l.y }

    const max=  {x: pixel_band.min, y :b_r.y }
    const max_t=  {x: pixel_band.min-100, y :b_r.y }

    const mid = {x: pixel_band.min-100, y :m_l.y }
    const mid_t=  {x: pixel_band.min, y :m_l.y }

    //console.log("mM",min,max)
    drawRect(ctx, min, max, "rgba(187, 187, 187, 0.1)", "rgba(187, 187, 187, 0.1)")

    drawTextOnLine(ctx, min, min_t , this.tp_price_txt, "white", 11, "right" , "green")
    drawTextOnLine(ctx, mid, mid_t , this.buy_price_txt, "white", 11, "right" , "blue")
    drawTextOnLine(ctx, max_t, max , this.sl_price_txt, "white", 11, "right" , "red")
   }
}


// ======================================================


export function  createPainter(context,mainChart,overlay) 
{
  return {
    context,
    overlay , 
    mainChart,
    active:false, drawing : false, start : null ,hovered:null,
    canvas_ctx : overlay.value.getContext('2d'), 
    dragHandle: null,   // "p1" | "p2"
    dragLine: null,
    drawMode : "trade-box",//"line",
    new_primitive:null,
    selected:null,
    edit:null,
    primitives : []

    ,setChart(chart,series){
      this.chart=chart;
      this.series=series;

      this.overlay.value.addEventListener('mousedown', e => {
        this.onMouseDown(e);
      })

      this.overlay.value.addEventListener('mousemove', e => {
        this.onMouseMove(e);
      })

      this.overlay.value.addEventListener('mouseup', e => {
        this.onMouseUp(e);
      })

      this.mainChart.value.addEventListener('contextmenu', e=>{
        e.preventDefault() // blocca menu browser
        console.log('right click', e)
        this.onRightClick(e)
      })

    }
    ,async load(){
       console.log( "load")
      try
      {
        const ind_response = await send_get(`/api/chart/read`,
          {"symbol":this.context.currentSymbol.value,"timeframe":this.context.currentTimeframe.value  });
          //ind_response.data = JSON.parse(ind_response.data)
        this.primitives.length=0;
        ind_response.map( data => {
              data.data = JSON.parse(data.data)
             //console.log( data)
              let prim = null
              if (data.data.type =="line")
                  prim = new Line(this)
               if (data.data.type =="box")
                  prim = new Box(this)
               if (data.data.type =="hline")
                  prim = new HLine(this)
                 if (data.data.type =="trade-box")
                  prim = new TradeBox(this)
              if (prim) 
              {
                  prim.fromSerial(data.data)
                  prim.guid = data.guid
                  this.primitives.push(prim)
              }
              
        })  
        this.redraw()
      }catch(e){
        console.error(e)
      }
    
    }
    ,clear(){
      this.primitives.forEach((p)=>{
          p.delete()
      })
      this.primitives.length=0;
      this.redraw();
    }
    ,pixelToChart(pos){
      const logical = this.chart.timeScale().coordinateToLogical(pos.x)
      const price = this.series.coordinateToPrice(pos.y)
      return { x: logical, y: price }
    }
    ,chartToPixel(pos){
      if (!pos) return {x:0,y:0}
      const x = this.chart.timeScale().logicalToCoordinate(pos.x)
      const y = this.series.priceToCoordinate(pos.y)
      return { x, y }
    }
    ,begin(){
        //console.log("begin")
        this.active = true
        this.overlay.value.style.pointerEvents = 'auto'
    }
    ,end(){
      this.active = false
      this.overlay.value.style.pointerEvents = 'none'
    }
    ,getMouse(e){
      const rect = this.overlay.value.getBoundingClientRect()
      return { x: e.clientX - rect.left, y: e.clientY - rect.top }
    }
    ,resizeOverlay(){
      this.overlay.value.width = this.mainChart.value.clientWidth
      this.overlay.value.height = this.mainChart.value.clientHeight
      this.redraw()
    }
    ,pick(pos){
      let o_p = null;
        this.primitives.forEach((p)=>{
        if (p.pick(pos))
        {
           o_p=p.pick(pos);
        }
       });
       return o_p;
    }
    ,getPriceBand(){
      return {min: this.overlay.value.width - 65 , max : this.overlay.value.width-10} 
    }
    // =========================================

    ,onMouseDown(e){
      if (this.edit)
        return
      console.log("mousedown",e)
      this.drawing=true
      this.edit=null
      this.selected=null
      this.start =  this.pixelToChart(this.getMouse(e))
      if (this.drawMode == "line"){
          this.new_primitive = new Line(this)
      }
      if (this.drawMode == "hline"){
          this.new_primitive = new HLine(this)
      }
      if (this.drawMode == "box"){
          this.new_primitive = new Box(this)
      }
      if (this.drawMode =="trade-box"){
          this.new_primitive = new TradeBox(this)
      }
       this.new_primitive.begin(this.start)
       this.redraw()
    }
    ,onMouseMove(e){
      if (!this.drawing) return

      if ( this.edit ){
        this.edit.drag( this.pixelToChart(this.getMouse(e)))
      }
      else{
          if (this.new_primitive) 
            this.new_primitive.drag( this.pixelToChart(this.getMouse(e)))
      }
       this.redraw()
    }
    ,onMouseUp(){
      this.drawing=false
      if (this.new_primitive) 
      {
        this.new_primitive.end()
        console.log("ADD")
        this.primitives.push(this.new_primitive)
      }
      this.new_primitive=null
      if (this.edit){
          this.edit.end()
      }
      this.edit =null
      this.end()
      this.redraw()
    
    }
    ,onMouseClick_disabled(){
      console.log("edit",this.selected)
      if (!this.selected) return false;

      console.log("edit")

      this.edit = this.selected;
      
      if (!this.edit.edit())
      {
        this.begin()
        this.drawing=true;
      }
      return true;
    }
    ,onMouseMove_disabled(mouse){

      this.hovered = null
      this.dragHandle=null
      
      this.selected = this.pick(mouse);
      
      //console.log("selected", this.selected)
    },

    onRightClick(){
      if (this.selected){
        // console.log("remove")
          window.dispatchEvent(new CustomEvent("edit-object", {
              detail: this.selected
            }))
            return true;
          /*
          send_delete("/api/chart/delete", {"guid": this.hovered.guid});
          const i = this.lines.findIndex(l => l.guid === this.hovered.guid)
          if(i !== -1) this.lines.splice(i,1)
          this.hovered=null
          this.redraw()
          */
      }
    }
    ,redraw(){
      this.canvas_ctx.clearRect(0,0,this.overlay.value.width,this.overlay.value.height)
      
      if (this.new_primitive) 
        this.new_primitive.draw(this.canvas_ctx)

      this.primitives.forEach((p)=>{
         p.draw(this.canvas_ctx)
      })
    },
  }
}