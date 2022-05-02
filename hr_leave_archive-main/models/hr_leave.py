from odoo import fields, models


class Leave(models.Model):
    _inherit = "hr.leave"

    active = fields.Boolean(default=True)
