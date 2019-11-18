from odoo import fields, models

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    po = fields.Char(
        string='PO',
    )
    require_po = fields.Boolean(
        related='partner_id.require_po',
    )
