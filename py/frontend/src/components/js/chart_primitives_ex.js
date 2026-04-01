/* eslint-disable no-unused-vars */
import {  Primitive} from '@/components/js/chart_primitives.js'; // Usa il percorso corretto
import { drawLine, drawRect, drawTextOnLine } from './chart_draw';
//import {  drawHandle,hitHandle,drawTextOnLine,hitLine,handleSize,drawLine,drawRect} from '@/components/js/chart_draw.js'; // Usa il percorso corretto
import { localUnixToUtc } from '@/components/js/utils.js'; // Usa il percorso corretto

const DAY_MINUTES = 1440

function getTimeZoneOffsetNY() {
    const now = new Date()

    const ny = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }))
    const local = new Date(now.toLocaleString("en-US"))

    const offsetMinutes = (local - ny) / 60000
    return offsetMinutes  // ?? ?
}

export  class MarketZoneBand  extends Primitive{

   constructor(painter,data){
    super(painter)
    this.data=data
    this.type = "market-zone"
    this.isHover = false
    this.color = '#ea00ff'
    this.zoneIndex = []
    this.onDataChanged()
    this.colors = {"close" : "#ff0000","pre" : "#e99269","open" : "#ffffff","after" : "#2963ad"}
    this.colors = {
        close: "rgba(255, 0, 0, 0.5)",
        pre: "rgba(248, 115, 5, 0.5)",
        open: "rgba(103, 212, 0, 0.92)",
        after: "rgba(41, 99, 173, 0.5)"
      };
  }
  onDataChanged() {


try{
      if (!this.data || this.data.length === 0)
      return
    
    const TIME_ZONE_OFFSET = getTimeZoneOffsetNY()
    //console.log("TIME_ZONE_OFFSET",TIME_ZONE_OFFSET)
    // LOCAL UTC
    const min_open = 9* 60 + 30
    const min_close = 16 * 60

    let zone = ""
    let old_zone = "close"
    let local_time = -1
    let ny_time = -1
    let old_time = -1
    let utc_time = -1;
    let idx=0

    this.zoneIndex = []
    this.lastClose = null
    this.lastOpen = null

    for (let i = 0; i < this.data.length; i++) {
      
      // UTC TIME
      local_time = this.data[i].time 
      ny_time = local_time-TIME_ZONE_OFFSET*60

      if (!local_time) continue

      // minuti UTC senza Date()
      let minutes = Math.floor(ny_time / 60) % DAY_MINUTES
      local_time = local_time *1000
      
      // console.log(minutes,minutes/60)
    
      if (minutes < 0)
        minutes += DAY_MINUTES

      if (minutes < min_open)
        zone = "pre"
      else if (minutes < min_close)
        zone = "open"
      else
        zone = "after"

      if (zone !== old_zone) {
        utc_time = localUnixToUtc(local_time)
        if (old_time !== -1) {

          if (zone === "after")
          {
            this.lastClose = i
          // console.log("after", this.data[i],local_time,ny_time)
          }

          if (zone === "open")
          {
            this.lastOpen = i
          //  console.log("OPEN", this.data[i],local_time,ny_time)
          }

          this.zoneIndex.push({
            from: old_time,
            to: utc_time,
            zone: old_zone
          })
        }

        old_zone = zone
        old_time = utc_time
      }
    }

    if (old_zone === "pre")
    {
      //console.log("kk")
      this.lastOpen = this.data.length-1// - 1
    }
    //else if (old_zone === "open" && this.zoneIndex.length > 0)
   //   this.lastOpen = this.zoneIndex[this.zoneIndex.length - 1].to

    this.zoneIndex.push({
      from: old_time,
      to: local_time,
      zone: old_zone
    })

    //console.log("zoneIndex",this.zoneIndex)
  }
     catch (ex){
        console.error(ex)
    }
  }


    draw(ctx){
    
        //console.log(this.data)
      const from = {x:0, y: this.painter.geHeight()-10}
      const to = {x:this.painter.getPriceBand().max, y: this.painter.geHeight()}

      this.zoneIndex.forEach( (zone)=>{
        // console.log("zone",zone)

          const f = this.painter.logicalToPixel({t: zone.from, y:0})
          const t = this.painter.logicalToPixel({t: zone.to, y:0})

          const p1 = {x:f.x, y: from.y}
          const p2 = {x:t.x, y: to.y}
          
      //   console.log(".:",zone.from,zone.to,p1,p2)

          drawRect(ctx,p1,p2, this.colors[zone.zone],
            this.colors[zone.zone],false,"solid"
          )
      });
    
      //console.log(from,to, log_from,log_to)
    }
      
    rebuild(){

    }
}

// =========================================

export  class GapZone  extends MarketZoneBand{
  
   constructor(painter,data){
    super(painter,data)
    this.type = "gap-zone"
    this.color =  "rgba(170, 145, 6, 0.9)"
   }
   onDataChanged(){
      super.onDataChanged()
      
      let m = 99999999
      let M = -99999999
      if (this.lastClose)
      {
       // console.log("close",this.data[this.lastClose])
       // console.log("open",this.data[this.lastOpen])

        for (var i = this.lastClose ; i<= this.lastOpen;i++)
        {
          if (!this.data[i]) continue
            m = Math.min(m, this.data[i].low)
            M = Math.max(M, this.data[i].high)
        }
        self.low = m
        self.hi = M
        self.middle = self.low + (self.hi-self.low)/2 
    }
        

  }

  draw(ctx){
      if (!this.lastClose) return
      const _lastClose = this.data[this.lastClose].close
      const _lastOpen = this.data[this.lastOpen].close
      
      const gapH = 100 * ( self.hi - self.low) /self.low ;
      const gap = 100 * ( _lastOpen - _lastClose) /_lastClose ;

      //const p1 = {x:0, y: _lastClose}
     // const p2 = {x:20, y: _lastOpen}

      const c = this.painter._chartToPixel({x: this.lastClose, y:_lastClose})
      const o = this.painter._chartToPixel({x: this.lastOpen, y:_lastOpen})
      const l = this.painter._chartToPixel({x: this.lastOpen, y:self.low })
      const h = this.painter._chartToPixel({x: this.lastOpen, y:self.hi })
      const m = this.painter._chartToPixel({x: this.lastOpen, y:self.middle })
      
       const p1 = {x:0, y: c.y}
       const p2 = {x:20, y: o.y}

    //  console.log("zone " , "l",self.low , "h", self.hi ,"c", _lastClose,"o",_lastOpen)
      //console.log(p1,p2,c,o,  l, h)

       drawRect(ctx,p1,p2,this.color ,this.color ,false,"solid")
       drawLine(ctx,  {x:10, y: l.y}, {x:10, y:  Math.max(o.y,c.y)}, this.color)
       drawLine(ctx,  {x:10, y: h.y}, {x:10, y: Math.min(o.y,c.y)},this.color)

       drawLine(ctx,  {x:20, y: m.y}, {x:30, y: m.y},"black")
       drawTextOnLine(ctx,{x:10, y: p2.y}, {x:10, y: p1.y}, `${gap.toFixed(0)} (${gapH.toFixed(0)}) %`, "black" , 0 )
    
  }
       
}

// ============

export  class OpenZoneBand  extends Primitive{
   constructor(painter,data){
    super(painter)
    this.data=data
    this.type = "open-zone"
    this.isHover = false
    this.colorBack = '#fbff002d'
    this.color = '#22eb2273'
    this.color_partial = '#ff00002d'
    this.zoneIndex = []
    this.onDataChanged()
  }

  openTimeUtc(){
     return localUnixToUtc( this.data[this.lastOpen].time)*1000
  }
  closeTimeUtc(){
     return localUnixToUtc( this.data[this.lastClose].time)*1000
  }
  openTimeIdx(){
     return this.lastOpen
  }
  priceHeight(){
    return this.max-this.min
  }
  setTP(value){
      console.log("TP",value)
  }  
  setSL(value){
    console.log("SL",value)
  }
  onDataChanged() 
  {
  try{
        if (!this.data || this.data.length === 0)
        return
      
      const TIME_ZONE_OFFSET = getTimeZoneOffsetNY()
  
      // LOCAL UTC
      const min_open = 9* 60 + 30
      const min_close = 9* 60 + 45
      const min_end = 10* 60  +30

      let local_time = -1
      let ny_time = -1

      this.lastClose = null
      this.lastOpen = null
      this.lastEnd = null
      this.isPartial=false;
      for (let i = 0; i < this.data.length; i++) {
        
        local_time = this.data[i].time 
        ny_time = local_time-TIME_ZONE_OFFSET*60

        if (!local_time) continue

        // minuti UTC senza Date()
        let minutes = Math.floor(ny_time / 60) % DAY_MINUTES
        local_time = local_time *1000
        
        //onsole.log("minutes",minutes)
        if (minutes < 0)
            minutes += DAY_MINUTES

        if (minutes == min_open )
        {
          this.lastOpen = i;
          this.lastClose = null
          this.lastEnd = null
        }
        if (this.lastOpen && minutes >= min_close && !this.lastClose)
          this.lastClose = i;
        if (this.lastClose && minutes >= min_end && !this.lastEnd)
          this.lastEnd = i;
      }
      if (!this.lastClose )
      {
        this.lastClose = this.data.length-1
        this.isPartial=true;
      }
      if (!this.lastEnd )
        this.lastEnd = this.data.length-1
      
      let m = 99999;
      let M = -99999
      for (let i= this.lastOpen;i<= this.lastClose;i++)
      {
        if (this.data[i])
        {
          m = Math.min(m , this.data[i].low)
          M= Math.max(M , this.data[i].high)
        }
      }
      this.min = m
      this.max = M
      //console.log("15m",this.lastOpen,this.lastClose,m,M)
    }
     catch (ex){
        console.error(ex)
    }
  }

  draw(ctx){
     if (!this.lastOpen) return

      const t1 = localUnixToUtc( this.data[this.lastOpen].time)*1000
      const t2 = localUnixToUtc( this.data[this.lastClose].time)*1000
      const t3 = localUnixToUtc( this.data[this.lastEnd].time)*1000
      
     //  console.log(t1,t2)
      const m = this.painter.logicalToPixel({t: t1, y:this.min})
      const M = this.painter.logicalToPixel({t: t2, y:this.max})

      const o = this.painter.logicalToPixel({t: t1, y:this.data[this.lastOpen].open})
      const c = this.painter.logicalToPixel({t: t2, y:this.data[this.lastClose].close})
      
      const p1_a = {x:m.x, y: m.y}
      const p2_a = {x:M.x, y: M.y}


      const p1 = {x:o.x, y: o.y}
      const p2 = {x:c.x, y: c.y}

    //  console.log("zone " , "l",self.low , "h", self.hi ,"c", _lastClose,"o",_lastOpen)
      //console.log(p1,p2,c,o,  l, h)
      drawRect(ctx,p1_a,p2_a,this.colorBack ,this.colorBack ,false,"solid")

      if (this.isPartial)
        drawRect(ctx,p1,p2,this.color_partial ,this.color_partial ,false,"solid")
      else
        drawRect(ctx,p1,p2,this.color ,this.color ,false,"solid")

      // DOWN
      const e = this.painter.logicalToPixel({t: t3, y:this.max})

      const p3 = {x:c.x, y: m.y}
      const p4 = {x:e.x, y: m.y}

      drawRect(ctx,p3,p4,"red" ,"red" ,false,"solid")

      // up
  
      const p5 = {x:c.x, y: M.y}
      const p6 = {x:e.x, y: M.y}

      drawRect(ctx,p5,p6,"green" ,"green" ,false,"solid")

      //console.log(from,to, log_from,log_to)
    }
      
    rebuild(){

    }
}
