from odoo import api, fields, models


class PlanningSlot(models.Model):
    _inherit = "planning.slot"

    department_id = fields.Many2one(
        related="employee_id.department_id",
        store=True,
    )
    add_department_id = fields.Many2one(
        comodel_name="hr.department",
    )
    employee_ids = fields.Many2many(
        string="Extra Employees",
        comodel_name="hr.employee",
    )

    @api.onchange("add_department_id")
    def _generate_employee_ids(self):
        if not self.add_department_id:
            self.employee_ids = []
            return
        self.employee_ids = self.add_department_id.member_ids

    @api.model_create_multi
    def create(self, vals_list):
        dicts = []
        for vals in vals_list:
            employee_ids = vals.pop('employee_ids', [])
            if not employee_ids:
                dicts.append(vals)
                continue
            real_employee_id = vals.pop("employee_id", None)
            real_employee_id = real_employee_id and [real_employee_id] or []
            dicts.extend([
                {**vals, "employee_id": employee_id}
                for employee_id in set(employee_ids[0][2] + real_employee_id) # Get IDS
            ])
        return super(PlanningSlot, self).create(dicts)[0]
