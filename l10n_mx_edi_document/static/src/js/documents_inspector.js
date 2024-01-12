odoo.define('l10n_mx_edi_document.DocumentsInspector', function( require ) {

    var DocumentsInspector = require('documents.DocumentsInspector');
    const {qweb} = require('web.core');

    DocumentsInspector.include({
        _renderFields: function() {
            this._super();
            var finance_folder = this.records.filter( function ( record ) {
                return record.data.in_finance_folder;
            });
            var show_customer = this.records.filter( function ( record ) {
                return record.data.show_customer_fields;
            });
            var show_analytic = this.records.filter( function ( record ) {
                return record.data.analytic_group;
            });
            const options = {mode: 'edit'};
            const proms = [];
            if (finance_folder.length > 0 && this.records.length > 0 && show_customer.length > 0) {
                proms.push(this._renderField('customer_journal_id', options));
                proms.push(this._renderField('customer_account_id', options));
            }
            if (finance_folder.length > 0 && this.records.length > 0) {
                proms.push(this._renderField('vendor_journal_id', options));
                proms.push(this._renderField('vendor_account_id', options));
                proms.push(this._renderField('invoice_date', options));
            }
            if (finance_folder.length > 0 && this.records.length > 0 && show_analytic.length > 0) {
                proms.push(this._renderField('analytic_account_id', options));
            }
        }
    });
});
