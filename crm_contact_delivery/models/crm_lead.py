from odoo import models


class CRMLead(models.Model):
    _inherit = "crm.lead"

    def _create_lead_partner_data(self, name, is_company, parent_id=False):
        res = super()._create_lead_partner_data(name, is_company, parent_id)
        res["type"] = "delivery"
        return res
