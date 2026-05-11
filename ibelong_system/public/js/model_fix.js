$(document).on('click', '.modal .close', function(e){
    e.preventDefault();
    const modal = $(this).closest('.modal')[0];
    try {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            let m = bootstrap.Modal.getInstance(modal) || new bootstrap.Modal(modal);
            m.hide();
        } else {
            $(modal).modal('hide');
        }
    } catch (err) {
        $(modal).hide();
    }
});
