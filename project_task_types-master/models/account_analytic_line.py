from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    line_type_id = fields.Many2one(
        comodel_name='account.analytic.line.type',
        string='Type'
    )
