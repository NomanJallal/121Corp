from odoo import _, api, fields, models


class AccountPaymentTax(models.Model):
    _name = "account.payment.tax"
    _description = "Linea impuestos"


    type_impuestos = fields.Selection(
        [('retencionesdr', 'Retencion DR'),
         ('trasladodr', 'Trasladado DR')],
        string="Retenciones")
    base = fields.Float(
        string='Base',
    )
    impuesto = fields.Char(
        string='Impuesto',
    )
    tipofactor = fields.Selection(
        selection=[
            ('Tasa', "Tasa"),
            ('Cuota', "Cuota"),
            ('Exento', "Exento"),
        ],
        string="Tipo de factor",
       )

    tasacuota = fields.Float(
        string='Tasacuota',
    )
    importe = fields.Float(
        string='Importe',
    )

    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
    )

    account_payment_id = fields.Many2one(
        'account.payment',
        string='Pago',
    )