from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_mx_edi_fuel_code_sat_ids = fields.Many2many(
        'product.unspsc.code', string='SAT fuel codes', readonly=False,
        related='company_id.l10n_mx_edi_fuel_code_sat_ids')
    l10n_mx_edi_import_customer_invoices = fields.Boolean('Import Customer Invoices?', readonly=False,
                                                          related='company_id.l10n_mx_edi_import_customer_invoices')
