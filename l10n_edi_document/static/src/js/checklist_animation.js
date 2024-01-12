odoo.define('l10n_edi_document.checklist_animation', function(require){
    'use strict';

    var AbstractField = require('web.AbstractField');

    AbstractField.include({
        _render: function () {
        this._super.apply(this, arguments);
            this.$el.find('.payments_checklist li').each(function(i) {
                $(this).delay(300 * i).fadeIn(800);
            });
        },
    });
});
