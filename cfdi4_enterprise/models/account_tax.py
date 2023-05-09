from odoo import _, api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.tax"

    impuestodr = fields.Selection(
        [('001', 'ISR'),
         ('002', 'IVA'),
         ('003', 'IEPS')],
        string="Impuestodr",)
