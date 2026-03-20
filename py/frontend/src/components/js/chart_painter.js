// eslint-disable-next-line no-unused-vars
import { send_get,localUnixToUtc,timeframeToSeconds,utcToLocalUnix } from '@/components/js/utils.js'; // Usa il percorso corretto
//formatUnixDate
import { ref,computed} from 'vue';
import {HLine,Box,Line,SplitBox,PriceLine,VLine,Fibonacci,
  MisureBox
 } from '@/components/js/chart_primitives.js'
 import {TradeBox, BuyAbove,BuyBelow,TradeRR
 } from '@/components/js/chart_primitives_trade.js'
 import {MarketZoneBand,GapZone ,OpenZoneBand} from '@/components/js/chart_primitives_ex.js'
import { liveStore } from '@/components/js/liveStore.js';



const trade_rr = computed(() => {
  return liveStore.get('trade.rr',1);
});

function cloneMouseEvent(e, type = e.type) {
  return new MouseEvent(type, {
    clientX: e.clientX,
    clientY: e.clientY,
    screenX: e.screenX,
    screenY: e.screenY,
    buttons: e.buttons,
    button: e.button,
    ctrlKey: e.ctrlKey,
    shiftKey: e.shiftKey,
    altKey: e.altKey,
    metaKey: e.metaKey,
    bubbles: true,
    cancelable: true,
  });
}  

function syncOverlaySize(overlay, topCanvas) {
      const rect = topCanvas.getBoundingClientRect();

      // dimensioni CSS
      if (overlay)
      {
      
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';

        // dimensioni reali canvas (importantissimo)
        overlay.width = rect.width * devicePixelRatio;
        overlay.height = rect.height * devicePixelRatio;

        // scala per retina
        const ctx = overlay.getContext('2d');
        ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      }
}

// ===========

export class ChartWatcher
{
  constructor(chart,painter, pollingTime){
     this.lastRangePrice=null;
     this.lastRangeTime=null;
     this.intervalId=null
     this.chart=chart;
     this.painter=painter;
     this.pollingTime=pollingTime
  }

  start(){
   
      const panes = this.chart.panes();

      // console.log("ChartWatcher start",panes)

      //if (!panes?.length) return;

      const priceScale = panes[0].priceScale("right");
      const ts = this.chart.timeScale();
  
      //console.log("ChartWatcher ..")

      this.intervalId=setInterval(()=>{
        try{
          let changed=false;

          const pr=priceScale.getVisibleRange?.();
          if(pr && (!this.lastRangePrice || pr.from!==this.lastRangePrice.from || pr.to!==this.lastRangePrice.to)){
            this.lastRangePrice=pr;
            changed=true;
          }

          const tr=ts.getVisibleLogicalRange?.();
          if(tr && (!this.lastRangeTime || tr.from!==this.lastRangeTime.from || tr.to!==this.lastRangeTime.to)){
            this.lastRangeTime=tr;
            changed=true;
          }

          if(changed) this.painter?.safeRedraw?.();
        }catch(e){console.debug(e)}
      },this.pollingTime)
    }
  destroy(){
  //  console.log("ChartWatcher destroy",this.intervalId)

    if (this.intervalId)
      clearInterval(this.intervalId)
  }
}

// ==============================================

export function  createPainter(context,mainChart,overlay, trade_quantity_ref) 
{
  return {
    context,
    overlay , 
    mainChart,
    //active:false, 
    drawing : false, start : null ,hovered:null,
    canvas_ctx : overlay.value.getContext('2d'), 
    dragHandle: null,   // "p1" | "p2"
    dragLine: null,
    drawMode : ref(""),//"line",
    new_primitive:null,
    selected:null,
    edit:null,
    primitives : [],
    chartCanvas:null,
    running:false,

    tradeBoxHandler: {add: null, change : null, delete : null},
    mouseHandler: {zoom: null},
    keyHandler: {down: null},
    //
    trade_quantity_ref : trade_quantity_ref,
    trade_RR_ref : trade_rr
   
    // ==================================
    
    ,_private__mouseEnterHandler(e){
       if (!this.isPaintEvent())
          this.chartCanvas.dispatchEvent(cloneMouseEvent(e));
    }
     ,_private__mouseLeaveHandler(e){
       if (!this.isPaintEvent())
          this.chartCanvas.dispatchEvent(cloneMouseEvent(e));
    }
    ,_private__mouseMoveHandler(e){
         if (!this.isPaintEvent())
          {
            //console.log("MOVE")
             const _new_selected = this.pick(this.getMouse(e));
             if (_new_selected != this.selected){
                this.selected = _new_selected
                 this.redraw()
                return
             }
             const evt = new MouseEvent('mousemove', {
                clientX: e.clientX,
                clientY: e.clientY,
                screenX: e.screenX,
                screenY: e.screenY,
                buttons: e.buttons,
                button: e.button,
                ctrlKey: e.ctrlKey,
                shiftKey: e.shiftKey,
                altKey: e.altKey,
                metaKey: e.metaKey,
                bubbles: true,
                cancelable: true,
              });

              this.chartCanvas.dispatchEvent(evt);
          }
          else
            this.onMouseMove(e);
      }
     ,_private__mouseDownHandler(e){
        if (!this.isPaintEvent())
          {
            if (this.selected) 
            {
                if (this.selected.isDraggable())
                {
                    this.edit = this.selected;
                    this.drawing=true;
                    this.drawMode.value="move"
                     this.onMouseDown(e);
                     return
                }
              }
            const evt = new MouseEvent('mousedown', e);
            this.chartCanvas.dispatchEvent(evt);
          }
          else
              this.onMouseDown(e);
    }
     ,_private__mouseUpHandler(e){
         if (!this.isPaintEvent())
          {    const evt = new MouseEvent('mouseup', e);
              this.chartCanvas.dispatchEvent(evt);
          }
          else
            this.onMouseUp(e);
    }
   ,_private__mouseWheelHandler(e){
        const evt = new WheelEvent('wheel', {
          deltaX: e.deltaX,
          deltaY: e.deltaY,
          deltaZ: e.deltaZ,
          clientX: e.clientX,
          clientY: e.clientY,
          ctrlKey: e.ctrlKey,
          shiftKey: e.shiftKey,
          altKey: e.altKey,
          metaKey: e.metaKey,
          bubbles: true,
          cancelable: true,
        });

         this.chartCanvas.dispatchEvent(evt);
         this.mouseHandler?.zoom()
         this.redraw();
    }
    ,_private__contextMenuHandler(e){
        e.preventDefault() // blocca menu browser
        console.log('right click', e)
        this.onRightClick(e)
      },

      _private__keyDownHandler(event) {
        //console.log("key",event)
        this.keyHandler?.down(event)
/*
        if (event.code === 'Space') {
            console.log('Space premuta');
        }
            */
      }

       // ==========================

      // 
      ,onTradeDataChanged(){
          this.primitives.forEach( (p)=>
          {
              p.update();
          });
          this.redraw()
      }
    // ==================================

    ,setMode(drawMode){
      this.drawMode.value=drawMode
    }
    ,clearMode(){
      this.drawMode.value=""
    }
    
    ,isPaintEvent(){
      return this.drawMode.value!= "" ;//|| this.selected!=null
    }

    // ==========================
    ,setData(data){
      this.data=data
   //   console.log("setData",data)
    }
    ,getData(){
      return this.data;
    }
    ,pushData(candle){
      if (this.data)
      {
        this.data.push(candle)
     //   console.log("pushData",this.data)

       this.primitives.forEach((p)=>{
            p.onDataChanged(this.data)
        })
        this.safeRedraw()
    }
    }
    /*
    , pushLastDataTime(time, dataLen){
      if (!this.lastData) this.lastData = time
      else if (time> this.lastData)
      {
        this.prevData=this.lastData
        this.lastData=time
      }
      this.dataLen=dataLen
     // console.log("setLastDataTime","p",this.prevData ,"l",this.lastData ,"len",this.dataLen)
    }
     */
    ,setChart(chart,series){
      this.chart=chart;
      this.series=series;
     
       this.overlay.value.style.pointerEvents = 'auto'

      // tv-lightweight-charts

      const chartContainer = this.mainChart.value.querySelector('.tv-lightweight-charts');
      const canvases = chartContainer.querySelectorAll('canvas');
      const topCanvas = [...canvases].find(c => {
        const z = parseInt(getComputedStyle(c).zIndex) || 0;
        return z === 2;
      });

      const ro = new ResizeObserver(() => {
        syncOverlaySize(this.overlay.value, topCanvas);
      });

      ro.observe(topCanvas);
      
      this.chartCanvas = topCanvas;
      // ===================
      this.overlay.value.tabIndex = 0;
      this.overlay.value.addEventListener('mouseenter', this._private__mouseEnterHandler.bind(this));
      this.overlay.value.addEventListener('mouseleave', this._private__mouseLeaveHandler.bind(this));
      this.overlay.value.addEventListener('mousedown',this._private__mouseDownHandler.bind(this));
      this.overlay.value.addEventListener('mousemove',this._private__mouseMoveHandler.bind(this));
      this.overlay.value.addEventListener('mouseup',this._private__mouseUpHandler.bind(this));
      this.overlay.value.addEventListener('wheel',this._private__mouseWheelHandler.bind(this));
      this.mainChart.value.addEventListener('contextmenu',this._private__contextMenuHandler.bind(this));
      this.overlay.value.addEventListener('keydown',  this._private__keyDownHandler.bind(this) );

      //this.begin()

    }
    ,unregister(){
       this.overlay.value.removeEventListener('mouseenter', this._private__mouseEnterHandler);
      this.overlay.value.removeEventListener('mouseleave', this._private__mouseLeaveHandler);
      this.overlay.value.removeEventListener('mousedown',this._private__mouseDownHandler);
      this.overlay.value.removeEventListener('mousemove',this._private__mouseMoveHandler)
      this.overlay.value.removeEventListener('mouseup',this._private__mouseUpHandler)
      this.overlay.value.removeEventListener('wheel',this._private__mouseWheelHandler);
      this.mainChart.value.removeEventListener('contextmenu',this._private__contextMenuHandler)
      this.overlay.value.removeEventListener('keydown',  this._private__keyDownHandler.bind(this) );
    }
    ,async load(){
      //console.log( "load")
      
      try
      {
        const ind_response = await send_get(`/api/chart/painter/read`,
          {"symbol":this.context.currentSymbol.value,"timeframe":this.context.currentTimeframe.value  });
          //ind_response.data = JSON.parse(ind_response.data)
        this.primitives.length=0;
        //this.primitives = this.primitives.filter(p => p.virtual !== false);

        ind_response.map( data => {
              data.data = JSON.parse(data.data)
           //  console.log( "load",data)
              let prim = null

              prim = this.create(data.data.type )
             
              if (prim) 
              {
                  prim.fromSerial(data.data)
                  prim.guid = data.guid
                  this.primitives.push(prim)
              }
              
        })  
        this.safeRedraw()
      }catch(e){
        console.error(e)
      }
    
    }
    ,clear(){
      this.primitives.forEach((p)=>{
        if (!p.virtual)
          p.delete()
      })
    // this.primitives.length=0;
      this.clearMode()
      this.redraw();
    }
    // =========
    ,pixelToLogical(pos){
        const p = this._pixelToChart(pos)
        return {"t": this._chartToTime(p),"y":p.y }
     }
    ,logicalToPixel(pos){
         if (!pos) return { x: 0, y: 0 };

          const ts = this.chart.timeScale();

          let time = utcToLocalUnix(pos.t)
          time=time/1000
          let x = ts.timeToCoordinate(time);

          if (x==null)
          {
              //x = this._timeToChart(t_l).x
                const vr = ts.getVisibleLogicalRange();
                const barSpacing = ts.options().barSpacing;
        
                const dt = timeframeToSeconds(this.context.currentTimeframe.value);

                const last = this.data[this.data.length-1];
                const first = this.data[0];

                const lastTime = last.time;
                const firstTime = first.time;

                let logical;

                if (time > lastTime) {
                  
                  // proiezione a destra
                  const factor = (time - lastTime) / dt;

                 //  console.log("time",time,"lastTime",lastTime,"f",factor,dt)

                  logical = (this.data.length - 1) + factor;
                }
                else {
                  // proiezione a sinistra
                  const factor = (firstTime - time) / dt;
                  logical = 0 - factor;
                }

                //const xFrom = ts.logicalToCoordinate(vr.from);
                x = ts.logicalToCoordinate(vr.from) + (logical - vr.from) * barSpacing;

              
          }
          
        //  console.log("logicalToPixel",pos.t,x)  
        
          const y = this.series.priceToCoordinate(pos.y);
       // console.log("logicalToPixel", pos , "_>", { x, y })

          return { x, y };
     }
    // =========
    ,_pixelToChart(pos){


      const logical = this.chart.timeScale().coordinateToLogical(pos.x)
      const price = this.series.coordinateToPrice(pos.y)

      //let t = ts.coordinateToTime(pos.x)
      /*
      const d = this.data[logical]
      if (d)
        console.log("time 11",d,formatUnixDate(d.time*1000))
      */
      return { x: logical, y: price }
    }
    ,_chartToPixel(pos){
      if (!pos) return {x:0,y:0}

      //console.log("chartToPixel",pos)
    
      const ts = this.chart.timeScale();

      const x0 = ts.logicalToCoordinate(0);
      const x1 = ts.logicalToCoordinate(1);
      const tickPx = x1 - x0;
      
      const vr = ts.getVisibleLogicalRange();

      const barSpacing = ts.options().barSpacing;
      const  x = tickPx/2 + ts.logicalToCoordinate(vr.from) + (pos.x-vr.from ) * barSpacing;
      const y = this.series.priceToCoordinate(pos.y);

      //console.log(pos,x,y)

      return { x, y };
    },
    _timeToChart(t){

        const ts = this.chart.timeScale();
        const vr = ts.getVisibleLogicalRange();
        const barSpacing = ts.options().barSpacing;

        // UTC -> local
        let local = utcToLocalUnix(t);

        // lightweight charts usa secondi
        const time = Math.floor(local / 1000);

        let x = ts.timeToCoordinate(time);

        if (x == null) {

          const dt = timeframeToSeconds(this.context.currentTimeframe.value);

          const last = this.data[this.data.length-1];
          const first = this.data[0];

          const lastTime = last.time;
          const firstTime = first.time;

          let logical;

          if (time > lastTime) {
            // proiezione a destra
            const factor = (time - lastTime) / dt;
            logical = (this.data.length - 1) + factor;
          }
          else {
            // proiezione a sinistra
            const factor = (firstTime - time) / dt;
            logical = 0 - factor;
          }

          //const xFrom = ts.logicalToCoordinate(vr.from);
          const xProj = ts.logicalToCoordinate(vr.from) + (logical - vr.from) * barSpacing;

          return { x: logical, px: xProj };
        }

        const xFrom = ts.logicalToCoordinate(vr.from);
        const logical = vr.from + (x - xFrom) / barSpacing;

        return { x: logical, px: x };
      }
    ,_chartToTime(pos){
      //console.log("chartToTime",pos)
      
      const ts = this.chart.timeScale();
      const vr = ts.getVisibleLogicalRange();

      const barSpacing = ts.options().barSpacing;
      const  x = ts.logicalToCoordinate(vr.from) + (pos.x-vr.from ) * barSpacing;
      // è in local time, la devo riportare in unix time

      let t = ts.coordinateToTime(x)
      if (t == null)
      {
        const dt = 1000* timeframeToSeconds(this.context.currentTimeframe.value)
         const xLast = ts.logicalToCoordinate(this.data.length-1);

       // const  last_x = ts.logicalToCoordinate(vr.from) + (pos.x-vr.from ) * barSpacing;

        const x0 = ts.logicalToCoordinate(0);
        const x1 = ts.logicalToCoordinate(1);
        const tickPx = x1 - x0;

        const factor = Math.round((x - xLast + tickPx/2)/tickPx);

        t =(this.data[this.data.length-1].time*1000)+ factor * dt

        //t = window.db_localTime(t)

       // console.log("...",dt,xLast, tickPx,"factor", factor )  
      }
      else
          t=t*1000

      t = localUnixToUtc(t)
      //console.log("chartToTime",x,t, formatUnixDate(t))
      return t;
    }
    ,begin(){
        //console.log("begin")
       // this.active = true
       // this.overlay.value.style.pointerEvents = 'auto'
    }
    ,end(){
      //this.active = false
      this.clearMode()
     // this.overlay.value.style.pointerEvents = 'none'
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
     ,geHeight(){
      const rect = this.chartCanvas.getBoundingClientRect();
      return rect.height;
    }
    ,getPriceBand(){
      const rect = this.chartCanvas.getBoundingClientRect();
      const a =  {min: rect.width -40 ,      max : rect.width} 
      return a;
    }
     // =========================================
    , onTradeBoxAdded(tradeBox){
        //console.log("onTradeBoxAdded",tradeBox)
         this.tradeBoxHandler.add(tradeBox)
    }
    ,subscribeTradeBoxAdded(handler)
    {
       this.tradeBoxHandler.add=handler
    }
    ,subscribeTradeBoxChanged(handler)
    {
       this.tradeBoxHandler.change=handler
    }
    ,subscribeTradeBoxDeleted(handler)
    {
       this.tradeBoxHandler.delete=handler
    }
     ,subscribeMouseZoom(handler)
    {
       this.mouseHandler.zoom=handler
    }
    ,subscribeKeyDown(handler)
    {
       this.keyHandler.down=handler
    }
    ,getTradeBox()
    {
        return this.primitives.find(p => p.isTradeMarker  );
    }
    ,getOpenZone()
    {
        return this.primitives.find(p => p.type =="open-zone"  );
    }
    ,updateTradeMarker(tradeMarkerData, isVirtual=false)
    {
       
       let box = this.getTradeBox()

       console.log("updateTradeMarker",tradeMarkerData,box)
       
       if (isVirtual && !box){
          //box = this.create("trade-box")
       }
       if (box)
       {
         // if (!tradeMarkerData.type)
          //  box.delete()

        //else
       // {
            box.tradeMarkerData=tradeMarkerData
            console.log("tradeMarkerData",tradeMarkerData)
      //  }
      }
      this.redraw()
       
    }
    // =========================================
    ,createVirtualVLine(timeIndex,color){
        const line = this.create("vline")
        line.color=color
        line.virtual=true
        line.style ="dotted"
        line.p.set({x:timeIndex , y:0})
        this.primitives.push(line)
    }
    ,createMarketZoneBand(){
         const line = new MarketZoneBand(this,this.data)
        line.virtual=true
        this.primitives.push(line)
    }
     ,createGapZone(){
         const line = new GapZone(this,this.data)
        line.virtual=true
        this.primitives.push(line)
    }
    ,createOpenZone(){
        const line = new OpenZoneBand(this,this.data)
        line.virtual=true
        this.primitives.push(line)
        return line
    }
    // =========================================

    , create(type){
        if (type == "line"){
          return new Line(this)
      }
      if (type== "hline"){
          return  new HLine(this)
      } 
     if (type== "vline"){
          return  new VLine(this)
      } 
      if (type == "price-line"){
          return new PriceLine(this)
      }
      if (type == "box"){
          return new Box(this)
      }
      if (type == "split-box"){
          return new SplitBox(this)
      }
       if (type == "misure-box"){
          return new MisureBox(this)
      }
       if (type  == "alarm-line")
            return new PriceLine(this)   
       if (type  == "fibonacci")
            return new Fibonacci(this)   
      if (type  == "buy-above")
            return new BuyAbove(this)   
      if (type  == "buy-below")
            return new BuyBelow(this)   
      if (type =="trade-box"){
          const exists = this.getTradeBox()
          if (!exists)
            return new TradeBox(this)
      }
       if (type =="trade-rr"){
         const exists = this.getTradeBox()
          if (!exists)
          {
            let t = new TradeRR(this)
            if (t.setup("bracket", ">"))
              return t
          }
      }
      return null
    }
    ,onMouseDown(e){
     // console.log("mousedown",e)

      if (this.edit)
        return

          
      this.drawing=true
      this.edit=null
      this.selected=null
      this.new_primitive=null;
      this.start =  this.pixelToLogical(this.getMouse(e))
      
      this.new_primitive = this.create(this.drawMode.value )
     
      if (this.new_primitive)
      {
       this.new_primitive.begin(this.start)
       
       this.redraw()
      }
    }
    ,onMouseMove(e){
      if (!this.drawing) return

      if ( this.edit ){
        this.edit.drag( this.pixelToLogical(this.getMouse(e)))
      }
      else{
          if (this.new_primitive) 
            this.new_primitive.drag( this.pixelToLogical(this.getMouse(e)))
      }
       this.redraw()
    }
    ,onMouseUp(){
      this.drawing=false
      let newTradeBox=null;
      let delTradeBox=null;
      if (this.new_primitive) 
      {
        if (this.new_primitive.isTradeMarker)
        {
            delTradeBox = this.getTradeBox()
            newTradeBox = this.new_primitive.isTradeMarker
        }
        this.new_primitive.end()
        this.primitives.push(this.new_primitive)
      }
      this.new_primitive=null
      if (this.edit){
          this.edit.end()
      }
      this.edit =null
      this.end()

      if (newTradeBox){
          if (delTradeBox)
            delTradeBox.delete()

          this.onTradeBoxAdded(newTradeBox)
      }
      this.safeRedraw()    
    }
    ,onDelete(guid){
      //console.log( this.primitives)
      const p =  this.primitives.find(p => p.guid === guid);
      this.primitives = this.primitives.filter(p => p.guid !== guid);
      if (p.type =="trade-box"){
          console.log("dleete nob")
          this.tradeBoxHandler.delete(p)
      }
      
      //console.log( this.primitives)

      //this.redraw()
    }
    ,onRightClick(){
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
    },
    safeRedraw(){
      if (this.running) return;
      this.running = true;
      requestAnimationFrame(()=>{
        this.redraw();
        this.running = false;
      });
    }
    ,redraw(){
      //console.trace()
      //console.log("redraw")
      if (!this.overlay.value) return
      this.canvas_ctx.save();
      this.canvas_ctx.setTransform(1, 0, 0, 1, 0, 0);
      this.canvas_ctx.clearRect(0,0,this.overlay.value.width,this.overlay.value.height)
      this.canvas_ctx.restore();

      //this.canvas_ctx.clearRect(0,0,this.overlay.value.width,this.overlay.value.height)
      
    if (this.new_primitive) 
      this.new_primitive.draw(this.canvas_ctx)

      this.primitives.forEach((p)=>{
         p.draw(this.canvas_ctx)
      })
    },
  }
}