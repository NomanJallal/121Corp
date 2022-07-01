from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    origin_id = fields.Many2one(
        comodel_name="sale.order",
        compute="_get_sale_order_origin",
    )
    po = fields.Char(
        related="origin_id.po",
        store=True,
    )

    @api.depends("invoice_origin")
    def _get_sale_order_origin(self):
        for r in self:
            r.origin_id = self.env["sale.order"].search([("name", "=", r.invoice_origin)], limit=1)
