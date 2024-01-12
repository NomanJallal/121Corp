# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_mx_edi_cfdi_uuid = fields.Char(
        'Fiscal Folio', compute='_compute_l10n_mx_edi_cfdi_uuid',
        search='_search_l10n_mx_edi_cfdi_uuid')

    @api.model
    def _name_search(self, name='', args=None, operator='ilike',
                     limit=100, name_get_uid=None):
        if args is None:
            args = []

        uuid_domain = self._search_l10n_mx_edi_cfdi_uuid(
            operator='=', value=name)
        payments = self.search(uuid_domain + args, limit=limit)
        res = payments.ids
        if not payments:
            res = super()._name_search(
                name, args, operator, limit, name_get_uid)
        return res

    def _search_l10n_mx_edi_cfdi_uuid(self, operator, value):
        attachments = self.env['ir.attachment'].search_read([
            ('res_model', '=', 'account.move'),
            ('l10n_mx_edi_cfdi_uuid', operator, value)], ['res_id'])
        payment_ids = [attachment['res_id'] for attachment in attachments]
        return [('move_id', 'in', payment_ids)]

    @api.depends('edi_document_ids')
    def _compute_l10n_mx_edi_cfdi_uuid(self):
        if not self.ids:
            self.l10n_mx_edi_cfdi_uuid = False
            return {}
        self.env.cr.execute("""
            SELECT res_id, l10n_mx_edi_cfdi_uuid
            FROM ir_attachment
            WHERE res_model = %s AND res_id IN %s
              AND l10n_mx_edi_cfdi_uuid IS NOT NULL
            ORDER BY create_date ASC, id ASC
        """, ('account.move', tuple(self.mapped('move_id').ids)))
        res = dict(self.env.cr.fetchall())
        for pay in self:
            pay.l10n_mx_edi_cfdi_uuid = res.get(pay.move_id.id)

    @api.constrains('edi_document_ids', 'state')
    def _check_invoice_uuid_duplicated(self):
        invoices = self.mapped('reconciled_invoice_ids').exists()
        if invoices:
            invoices.sudo()._check_uuid_duplicated()
