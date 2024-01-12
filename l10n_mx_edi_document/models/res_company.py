from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_edi_fuel_code_sat_ids = fields.Many2many(
        'product.unspsc.code', string='SAT fuel codes', domain=[('applies_to', '=', 'product')])
    l10n_mx_edi_import_customer_invoices = fields.Boolean(
        'Import Customer Invoices?', help='If the company is starting in Odoo, and must import the open customer '
        'invoices, mark this option to allow select the default journal and account to be used in Documents.')
