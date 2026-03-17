/* eslint-disable no-unused-vars */
import {  Primitive} from '@/components/js/chart_primitives.js'; // Usa il percorso corretto
import { drawLine, drawRect, drawTextOnLine } from './chart_draw';
//import {  drawHandle,hitHandle,drawTextOnLine,hitLine,handleSize,drawLine,drawRect} from '@/components/js/chart_draw.js'; // Usa il percorso corretto
import { localUnixToUtc } from '@/components/js/utils.js'; // Usa il percorso corretto

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
    const DAY_MINUTES = 1440

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
