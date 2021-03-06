/* Welborn Productions - img - Javascript
    Provides tools on the client-side for the img app.
    -Christopher Welborn 2-2-15
*/

/*  JSHint/JSLint options:
    `wptools` is a read-only global.
*/
/* global wptools:false */

var imgtools = { // eslint-disable-line no-unused-vars
    // Modules and file names are versioned to "break" the cache on updates.
    version: '0.0.3',
    do_upload : function () {
        if (!$('#upload-image').val()) {
            wptools.wpalert('You must select a file first.');
            return;
        }
        wptools.pre_ajax();
        $('#upload-form').submit();
        $('#img-upload-form-floater').fadeOut();
    },

    init_upload_floater : function () {
        /* Initialize the upload form for admins. */
        $(document).ready(function () {
            var $floater = $('#img-upload-form-floater');
            wptools.center($floater, true);
            $floater.draggable({'scroll': true, 'axis': 'y'});
            $floater.dblclick(function () {
                wptools.center($floater, true);
            });

            $('#upload-file').required = true;
        });
    },

    toggle_upload_form : function () {
        var $uploadfloater = $('#img-upload-form-floater');
        if ($uploadfloater.css('display') === 'none') {
            // Only center when showing the form.
            wptools.center($uploadfloater, true);
        }
        $uploadfloater.fadeToggle();
    },
};
