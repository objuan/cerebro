import { send_get,send_delete, send_post } from '@/components/js/utils.js'; // Usa il percorso corretto
//generateGUID
const handleSize=6

function drawTextOnLine(ctx, a, b, text, color = "white", offset = 10) {
    // punto medio
    const midX = (a.x + b.x) / 2;
    const midY = (a.y + b.y) / 2;

    // angolo della linea
    const angle = Math.atan2(b.y - a.y, b.x - a.x);

    ctx.save();

    // sposta al punto medio
    ctx.translate(midX, midY);

    // ruota come la linea
    ctx.rotate(angle);

    // disegna sopra la linea (offset verticale)
    ctx.fillStyle = color;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(text, 0, -offset);

    ctx.restore();
}

function  drawLine(ctx, a,b,hover=false){
      ctx.beginPath()
      ctx.moveTo(a.x,a.y)
      ctx.lineTo(b.x,b.y)
      ctx.strokeStyle = hover ? 'yellow' : 'white'
      ctx.lineWidth = hover ? 2 : 1
      ctx.stroke()
}
function drawRect(ctx, a, b, hover=false, fillColor='rgba(255,255,255,0.2)'){
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
    ctx.strokeStyle = hover ? 'yellow' : 'white'
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

export function  createHandle(painter, parent) {
  return {
    type:"handle",
    painter,
    parent
    , val:null
    , isHover: false
    ,set(p){
      this.val=p
    }
    ,draw(ctx){
      const a = this.painter.chartToPixel(this.val)
      drawHandle(ctx, a, this.isHover)
    }
    ,drag(pos){
       pos = this.parent.filter(this,pos)
       this.val=pos
    }
    ,pick(pos){
      this.isHover=false
      const a = this.painter.chartToPixel(this.val)
        if (hitHandle(pos,a)){
            this.isHover=true
        }
        if (this.isHover)
          return this;
        else
          return null;
    }
  }
}

export function createLine(painter) {

  const line = {
    type:"line",
    painter,
    p1:null,
    p2:null,
    isHover:false,

    begin(p1){
      this.p1.set(p1)
      this.p2.set(p1)
    },

    drag(p2){
      p2 = this.filter(this.p2,p2)
      this.p2.set(p2)
    },

    end(){},

    filter(p,new_pos){
      return new_pos
    },

    draw(ctx){
      const a = this.painter.chartToPixel(this.p1.val)
      const b = this.painter.chartToPixel(this.p2.val)
      drawLine(ctx,a,b,this.isHover)

      if(this.isHover){
        this.p1.draw(ctx)
        this.p2.draw(ctx)
      }
    },

    pick(pos){
      const a = this.painter.chartToPixel(this.p1.val)
      const b = this.painter.chartToPixel(this.p2.val)

      this.isHover=false

      if(hitLine(pos,a,b))
        this.isHover=true

      if(this.p1.pick(pos)) return this.p1
      if(this.p2.pick(pos)) return this.p2
      if(this.isHover) return this

      return null
    }
  }

  // 👉 QUI this esiste (line)
  line.p1 = createHandle(painter,line)
  line.p2 = createHandle(painter,line)

  return line
}

// ============

export function createBox(painter) {
 return {
    type:"box",
    painter,
    p1:createHandle(painter),
    p2:createHandle(painter),
    isHover:false,
   // dragHandle: null  

    begin(p1){
      this.p1.set(p1)
      this.p2.set(p1)
    }
    ,drag(p2){
      this.p2.set(p2)
    }
    ,end(){
    }
    ,draw(ctx){

        const a = this.painter.chartToPixel(this.p1.val)
        const b = this.painter.chartToPixel(this.p2.val)
        drawRect(ctx, a,b,this.isHover )

        if (this.isHover){
            this.p1.draw(ctx)
            this.p2.draw(ctx)
        }
    },
    pick(pos){

      this.isHover=false;

       if (this.p1.pick(pos))
        return this.p1;

       if (this.p2.pick(pos))
        return this.p2;
       
       if ( this.isHover)
        return this;
      return null;
      
    }
 }
}

// ======

export function createHLine(painter) {
  let line =  createLine(painter);
  line.type="hline";
  line.filter = (p, new_pos)=>{
    const other = line.p1 == p ? line.p2 : line.p1;
    new_pos.y = other.val.y
    //console.log(p,other,new_pos)
    return new_pos
  }
  return line;
}

export function createTradeArea(painter) {
 return {
    type:"tradeLine",
    painter,
    high:createHandle(painter),
    low:createHandle(painter),
    middle:createHandle(painter),
    isHover:false,

    begin(p1){
      this.high.set(p1)
      this.middle.set(p1)
      this.low.set(p1)
    }
    ,drag(p2){
      this.high.set(p2)
      this.low.set(p2)
      //let m = Math.abs()
      this.middle.set(p2)
    }
    ,end(){
    }
    ,draw(ctx){

        const h = this.painter.chartToPixel(this.high.val)
       // const m = this.painter.chartToPixel(this.middle.val)
        const l = this.painter.chartToPixel(this.low.val)
        drawRect(ctx, h,l,this.isHover )

        if (this.isHover){
            this.h.draw(ctx)
            this.l.draw(ctx)
        }
    },
    pick(pos){

      this.isHover=false;

       if (this.high.pick(pos))
        return this.high;

       if (this.low.pick(pos))
        return this.low;
       
       if ( this.isHover)
        return this;
      return null;
      
    }
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
    lines : [],
    dragHandle: null,   // "p1" | "p2"
    dragLine: null,
    drawMode : "line",//"line",
    current:null,
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
      //  console.log( "load")
      
      const ind_response = await send_get(`/api/chart/read`,
        {"symbol":this.context.currentSymbol.value,"timeframe":this.context.currentTimeframe.value  });
        //ind_response.data = JSON.parse(ind_response.data)
      this.lines.length=0;
      ind_response.map( data => {
            data.data = JSON.parse(data.data)
        //   console.log( data.data)

            if (data.data.type =="line"){

              const line =  { 
                  guid : data.guid,
                  p1 : data.data.p1,
                  p2: data.data.p2
                }
              //console.log( "load",line)
              this.lines.push(line)
            }
      })  
    }
    ,save(line){
      send_post("/api/chart/save",
      {
          symbol: this.context.currentSymbol.value,
          timeframe: this.context.currentTimeframe.value,
          guid: line.guid,
          data: 
          {  
              "type": "line",
              "p1": line.p1,
              "p2":  line.p2,
              "color": '#ffcc00',
          }
        });
    }
    ,clear(){
      this.lines.length=0;
      this.redraw();
    }
    ,pixelToChart(pos){
      const logical = this.chart.timeScale().coordinateToLogical(pos.x)
      const price = this.series.coordinateToPrice(pos.y)
      return { x: logical, y: price }
    }
    ,chartToPixel(pos){
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
    , pick(pos){
      let o_p = null;
        this.primitives.forEach((p)=>{
        if (p.pick(pos))
        {
           o_p=p.pick(pos);
        }
       });
       return o_p;
    }
    // =========================================

    ,onMouseDown(e){
    // console.log("mousedown",e)
      this.drawing=true
      this.start =  this.pixelToChart(this.getMouse(e))
      if (this.drawMode == "line"){
          this.current = createLine(this)
          this.current.begin(this.start)
      }
      if (this.drawMode == "hline"){
          this.current = createHLine(this)
          this.current.begin(this.start)
      }
      if (this.drawMode == "box"){
          this.current = createBox(this)
          this.current.begin(this.start)
      }
      if (this.drawMode =="tradeArea"){
           this.current = createTradeArea(this)
           this.current.begin(this.start)
      }
       this.redraw()
    }
    ,onMouseMove(e){
      if (!this.drawing) return

      if ( this.edit ){
        this.edit.drag( this.pixelToChart(this.getMouse(e)))
      }
      else{
          if (!this.current) return
          this.current.drag( this.pixelToChart(this.getMouse(e)))
      }
       this.redraw()
    }
    ,onMouseUp(){
      this.drawing=false
      if (this.current) 
      {
        this.current.end()

        this.primitives.push(this.current)
        this.current=null
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
    
      this.begin()
      this.drawing=true;
       return true;
    }
    ,onMouseMove_disabled(mouse){

      this.hovered = null
      this.dragHandle=null
      
      this.selected = this.pick(mouse);
      
      console.log("selected", this.selected)
    },

    onRightClick(){
      if (this.hovered){
        // console.log("remove")
          
          send_delete("/api/chart/delete", {"guid": this.hovered.guid});
          const i = this.lines.findIndex(l => l.guid === this.hovered.guid)
          if(i !== -1) this.lines.splice(i,1)
          this.hovered=null
          this.redraw()
      }
    }
    ,redraw(){
      this.canvas_ctx.clearRect(0,0,this.overlay.value.width,this.overlay.value.height)
      
      if (this.current) 
        this.current.draw(this.canvas_ctx)

      this.primitives.forEach((p)=>{
         p.draw(this.canvas_ctx)
      })
    },
  }
}