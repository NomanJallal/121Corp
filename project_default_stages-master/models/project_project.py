from odoo import models, fields

class ProjectProject(models.Model):
    _inherit = 'project.project'
    
    def _get_all_types(self):
        return self.env['project.task.type'].search([], limit=5)

    type_ids = fields.Many2many(
        string="Tasks Stages",
        comodel_name="project.task.type",
        relation="project_task_type_rel",
        column1="project_id",
        column2="type_id",
        default=_get_all_types,
    )
