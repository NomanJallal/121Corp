odoo.define('l10n_mx_edi_document.documents_dashboard', (require) => {

    const Kanban = require('documents.DocumentsKanbanView');

    Kanban.include({
        init() {
            this._super.apply(this, arguments);
            _.defaults(this.fieldsInfo[this.viewType], _.pick(this.fields, [
                'in_finance_folder',
                'customer_journal_id',
                'vendor_journal_id',
                'customer_account_id',
                'vendor_account_id',
                'invoice_date',
                'show_customer_fields',
                'analytic_account_id',
                'analytic_group',
            ]));
        }
    });

    return Kanban;
});
