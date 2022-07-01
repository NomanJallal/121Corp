from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    department_id = fields.Many2one(
        comodel_name="hr.department",
        compute="_compute_department_id",
        store=True,
        readonly=False,
    )

    @api.depends("user_id")
    def _compute_department_id(self):
        for record in self:
            if record.user_id:
                record.department_id = record.user_id.department_id
