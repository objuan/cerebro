
// =============== CHART ===============


function createChart(widget_ele,id_chart, symbol, timeframe,plot_config) {
    const container = document.getElementById(id_chart);
    //console.log("container",container)

    const legend = document.createElement('div');
    legend.className = 'chart-legend';
    
    //legend.style = `position: absolute; left: 12px; top: 12px; z-index: 1; font-size: 14px; font-family: sans-serif; line-height: 18px; font-weight: 300;`;
    container.appendChild(legend);

    // MAIN 
    const chart = LightweightCharts.createChart(container, {
        layout: {
            background: { color: '#253248' },
            textColor: 'rgba(255, 255, 255, 0.9)',
        },
        grid: {
            vertLines: { color: '#334158' },
            horzLines: { color: '#334158' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            // Vertical crosshair line (showing Date in Label)
            vertLine: {
                width: 1,
                color: '#C3BCDB44',
                style: LightweightCharts.LineStyle.Solid,
                labelBackgroundColor: '#9B7DFF',
            },

            // Horizontal crosshair line (showing Price in Label)
            horzLine: {
                height: 1,
                color: '#9B7DFF',
                labelBackgroundColor: '#9B7DFF',
            },
        },
        priceScale: { borderColor: '#485c7b' },
        timeScale: { borderColor: '#485c7b' },
        timeScale: {
            timeVisible: true,
            secondsVisible: false,
            borderColor: '#485c7b',
        },
    });

    
    const mainSeries = chart.addSeries(
        LightweightCharts.CandlestickSeries,
        {
            upColor: '#4bffb5',
            downColor: '#ff4976',
            borderUpColor: '#4bffb5',
            borderDownColor: '#ff4976',
            wickUpColor: '#838ca1',
            wickDownColor: '#838ca1',
        }
    );

    
    // SUB VOLUME
    const chart2 = LightweightCharts.createChart(
        document.getElementById(id_chart),
        {
            height: 100,
            layout: {
                background: {
                    type: 'solid',
                    color: '#F5F5FF',
                },
            },
         timeScale: {
            timeVisible: true,
            secondsVisible: false,
            borderColor: '#485c7b',
        },
        }
    );

    const volumeSeries = chart2.addSeries(
        LightweightCharts.HistogramSeries,
        {
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: '', // 👈 scale separata sotto
            scaleMargins: {
            top: 0.7,
            bottom: 0,
            },
        }
        );

    // INDICATORS
    const indicators = []

    Object.entries(plot_config["main_plot"]).forEach(([key, value]) => {
        //console.log("ADD" , key, value);
        if (value["fun"] == "ema")
        {
           indicators[key] = {
              fun : calculateEMA,
              args : value["eta"],
              color : value["color"],
              series : chart.addSeries(
                LightweightCharts.LineSeries,
                {
                    color:  value["color"],
                    lineWidth: 1,
                }
              )
          }
          indicators[key].series.applyOptions({
                lastValueVisible: false,
            });
        }
        
    });

    // SYNC

    chart.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        chart2.timeScale().setVisibleLogicalRange(timeRange);
    });

    chart2.timeScale().subscribeVisibleLogicalRangeChange(timeRange => {
        chart.timeScale().setVisibleLogicalRange(timeRange);
    });

    
    function getCrosshairDataPoint(series, param) {
        if (!param.time) {
            return null;
        }
        const dataPoint = param.seriesData.get(series);
        return dataPoint || null;
    }

    function syncCrosshair(chart, series, dataPoint) {
        if (dataPoint) {
            chart.setCrosshairPosition(dataPoint.value, dataPoint.time, series);
            return;
        }
        chart.clearCrosshairPosition();
    }
    chart.subscribeCrosshairMove(param => {
        const dataPoint = getCrosshairDataPoint(mainSeries, param);
        syncCrosshair(chart2, volumeSeries, dataPoint);

        lbl="";
        if (param.time && dataPoint) {
            let priceFormatted = '';
            const price =  dataPoint.close;
            priceFormatted = price.toFixed(3);

            o_formatted = dataPoint.open.toFixed(3);
            h_formatted = dataPoint.high.toFixed(3);
            l_formatted = dataPoint.low.toFixed(3);

          
            //console.log(param.seriesData)
            //const volume = param.seriesPrices.get(volumeSeries);

            v_formatted=""
            //if (volume != undefined) 
            //    v_formatted = vPoint.value
        
            // legend is a html element which has already been created
            lbl=`C:<strong>${priceFormatted}</strong> O:<strong>${o_formatted}</strong> L:<strong>${l_formatted}</strong> H:<strong>${h_formatted}</strong> V:<strong>${v_formatted}</strong>`
            
            Object.entries(indicators).forEach(([key, chartMeta]) => {
               // const valPoint = getCrosshairDataPoint(chartMeta["series"],param)
                const valPoint = param.seriesData.get(chartMeta["series"]);
                //valPoint = valPoint || null
                if (valPoint)
                  lbl+= ` <span style='color:${chartMeta["color"]}'>` +key+" " + valPoint.value.toFixed(3)+"</span>";
            });
        }
        
        legend.innerHTML = lbl;
    });
    chart2.subscribeCrosshairMove(param => {
        const dataPoint = getCrosshairDataPoint(volumeSeries, param);
        syncCrosshair(chart, mainSeries, dataPoint);
    });

    // final

      function refresh()
      {
        //console.log("....",this);
          fetch(`/api/ohlc_chart?symbol=${this.symbol}&timeframe=${this.timeframe}`)
            .then(r => r.json())
            .then(data => {
                console.log(data)
               if (data.length>0)
               {
                  this.mainSeries.setData(
                      data.map(d => ({
                      time: db_localTime(d.t),
                      open: d.o,
                      high: d.h,
                      low: d.l,
                      close: d.c
                      }))
                  );
                  this.volumeSeries.setData(
                      data.map(d => ({
                          time: db_localTime(d.t),
                          value: d.bv,
                          color: d.c >= d.o ? '#4bffb5aa' : '#ff4976aa'
                      }))
                  );

                  Object.entries(this.indicators).forEach(([key, chartMeta]) => {
                      //console.log("REFRESH", key, chartMeta);
                      const ind_data = chartMeta["fun"]( data, chartMeta["args"]);
                      //console.log(ind_data)
                      chartMeta["series"].setData(ind_data);
                  });

                  const barsToShow = 50;
                  const totalBars = data.length;
                  chart.timeScale().setVisibleLogicalRange({
                     from: totalBars - barsToShow,
                    to: totalBars,
                     //   from: data[0].time,
                      //  to: data[data.length - 1].time
                    });
                    
                  //chart.timeScale().fitContent();
                }
            });
      }
      function save()
      {
        //alert("save");
        return {"symbol":this.symbol,"timeframe":this.timeframe,"plot_config": this.plot_config}
      }

    chart_list[id_chart] = { id : id_chart, widget_ele:widget_ele, symbol:symbol, timeframe:timeframe, charts:[chart,chart2], mainSeries ,volumeSeries: volumeSeries, 
      plot_config:plot_config, indicators : indicators, refresh: refresh , save:save};

    chart_map[symbol] = chart_list[id_chart] ;
    widget_list.push(chart_list[id_chart]);

    //console.log("!!!!!!!!!!",widget_list);
    // EXTRA

    /**
     * Funzione di utilità per convertire una coordinata Y in prezzo.
     * @param {number} yCoordinate - La coordinata Y in pixel relativa al riquadro del grafico.
     * @returns {number|null} Il prezzo corrispondente.
     */
    function convertCoordinateToPrice(yCoordinate) {
        if (mainSeries) {
            return mainSeries.coordinateToPrice(yCoordinate); 
        }
        return null;
    }

    container.addEventListener('contextmenu', function(event) {
      event.preventDefault(); // Impedisce la comparsa del menu contestuale del browser

      // Qui devi convertire le coordinate, vedi il punto 2
      const clientX = event.clientX;
      const clientY = event.clientY;

      // Ottieni le coordinate relative al grafico
      const chartRect = container.getBoundingClientRect();
      const chartY = clientY - chartRect.top;
      
      // Converti la coordinata Y in prezzo
      // Chiama la funzione di conversione (vedi sotto)
      const priceAtMouse = convertCoordinateToPrice(chartY); 

      console.log(`Evento Tasto Destro a coordinata Y del grafico: ${chartY}`);
      console.log(`Prezzo corrispondente: ${priceAtMouse}`);

      // Logica per mostrare il tuo menu contestuale al clientX/clientY
      
     
  });

 chart_list[id_chart] .refresh();

 return chart_list[id_chart];
}

