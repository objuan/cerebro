
function createReport(widget_ele,id, report_data) {
    const container = document.getElementById(id);
   
    report_obj = {
        report_data : report_data,
        save: ()=>
        {
            //alert("save");
            return {
                "type": "report",
                "report_type": "top_gain"}
        },
        update : (data)=>
        {
            const table =$(`#${id}`).DataTable();
            table.clear();
            table.rows.add(data);
            table.draw(false);

            //console.log(data)
        }
        
    }
    
    //console.log("container",widget_ele,container)

    report_map[id] = report_obj
    widget_list.push(report_obj);

    columnDefs = []
    let table = $(`#${id}`)
    table.colorFun = []
    table.formatFun = []
    for(i=0;i<report_data.columns.length;i++)
    {
        /*
        //console.log("ii ",report_data.columns[i])
        if (report_data.columns[i].decimals){
             table.formatFun.push(report_data.columns[i].decimals);
        }
        else{
            table.formatFun.push(null);
        }
        
        if (report_data.columns[i].colors){
            const colors = report_data.columns[i].colors ;
            const decimals = report_data.columns[i].colors ;
            
            table.colorFun.push( (value,td,cellData)=>
            {
                range_min = colors["range_min"]
                range_max = colors["range_max"]
                factor = Math.min(1, (Math.max(0,value - range_min) / (range_max- range_min)));
                col = interpolateColor(colors["color_min"],colors["color_max"], factor);  
                console.log("find ",range_min,range_max, factor)
                 $(td).css('background-color', col); // green
                 $(td).css('color', "black"); 
            });
            //console.log("find ",i,colors)
        }
        else
            table.colorFun.push(null); 
*/
        //if (report_data.columns[i].colors || report_data.columns[i].decimals)
        {
            const colors = report_data.columns[i].colors ;
            const decimals = report_data.columns[i].decimals ;
            const type = report_data.columns[i].type ;
          
            columnDefs.push(
             {
                    target : i,
                    createdCell: function (td, cellData, rowData, row, col) {
                        
                        if (!type)
                        {
                            value = parseFloat(cellData);
                            if (decimals)
                            {
                                value =  value.toFixed(decimals);
                            }

                            let api = this.api();
                            api.cell(row,col).data(formatValue(value));

                            
                            if (colors)
                            {
                                range_min = colors["range_min"]
                                range_max = colors["range_max"]
                                factor = Math.min(1, (Math.max(0,value - range_min) / (range_max- range_min)));
                                col = interpolateColor(colors["color_min"],colors["color_max"], factor);  
                                //console.log("find ",range_min,range_max, factor)
                                $(td).css('background-color', col); // green
                                $(td).css('color', "black"); 
                            }
                        }
                    }
                }
                
            )
        }
    }
    //console.log(columnDefs);

      
      $(`#${id}`).DataTable({
            columnDefs: columnDefs,
            columns:report_data.columns,
            searching: false, paging: false, info: false
      });

}

