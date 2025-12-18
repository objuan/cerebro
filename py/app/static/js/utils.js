function PopupList(list,current, onclose)
{
    const sel = $('#choice').empty();
    $.each(list, function (_, v) {
          $('<option>').val(v).text(v)
            .prop('selected', v === current).appendTo(sel);
    });
    $('#popup').show();

    $('#cancel').on('click', function () {
        $('#popup').hide();
    });

    $('#ok').on('click', function () {
       // alert('Hai scelto: ' + $('#choice').val());
        onclose($('#choice').val())
        $('#popup').hide();
    });


}

function bind_get(id , variable, formatFun)
{
    
}
