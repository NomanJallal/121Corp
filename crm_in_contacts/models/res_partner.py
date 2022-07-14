from odoo import api, fields, models


class Partner(models.Model):
    _inherit = "res.partner"

    last_crm_lead_id = fields.Many2one(
        comodel_name="crm.lead",
        readonly=True,
    )
    last_crm_lead_date = fields.Datetime(
        related="last_crm_lead_id.create_date",
        string="Last Opportunity",
    )
    last_activity_date = fields.Datetime(
        related="last_crm_lead_id.last_activity_date",
        string="Last Activity",
    )
    last_activity_type_name = fields.Char(
        related="last_crm_lead_id.last_activity_type_name",
        string="Type Activity",
    )
