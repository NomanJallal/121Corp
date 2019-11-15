from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    require_po = fields.Boolean(
    )