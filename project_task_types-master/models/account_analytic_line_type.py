from odoo import api, fields, models


class AccountAnalyticLineType(models.Model):
    _name = 'account.analytic.line.type'

    name = fields.Char(
        compute='_get_name',
        store=True,
    )
    code = fields.Char(
        required=True,
    )
    description = fields.Char(
        required=True,
    )
    
    @api.depends('code', 'description')
    def _get_name(self):
        for r in self:
            r.name = '{code} - {description}'.format(code=r.code, description=r.description)
    
    
    
