from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_mx_edi_domicilio_fiscal = fields.Char(string="Domicilio Fiscal Receptor", copy=False)

    l10n_mx_edi_fiscal_regime = fields.Selection(
        [('601', 'General de Ley Personas Morales'),
         ('603', 'Personas Morales con Fines no Lucrativos'),
         ('605', 'Sueldos y Salarios e Ingresos Asimilados a Salarios'),
         ('606', 'Arrendamiento'),
         ('607', 'Régimen de Enajenación o Adquisición de Bienes'),
         ('608', 'Demás ingresos'),
         ('609', 'Consolidación'),
         ('610', 'Residentes en el Extranjero sin Establecimiento Permanente en México'),
         ('611', 'Ingresos por Dividendos (socios y accionistas)'),
         ('612', 'Personas Físicas con Actividades Empresariales y Profesionales'),
         ('614', 'Ingresos por intereses'),
         ('615', 'Régimen de los ingresos por obtención de premios'),
         ('616', 'Sin obligaciones fiscales'),
         ('620', 'Sociedades Cooperativas de Producción que optan por diferir sus ingresos'),
         ('621', 'Incorporación Fiscal'),
         ('622', 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras'),
         ('623', 'Opcional para Grupos de Sociedades'),
         ('624', 'Coordinados'),
         ('625', 'Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas'),
         ('626', 'Régimen Simplificado de Confianza - RESICO')],
        string="Regimen Fiscal",)

    l10n_mx_edi_usage = fields.Selection(
        selection=[
            ('G01', 'Adquisición de mercancías.'),
            ('G02', 'Devoluciones, descuentos o bonificaciones.'),
            ('G03', 'Gastos en general.'),
            ('I01', 'Construcciones.'),
            ('I02', 'Mobiliario y equipo de oficina por inversiones.'),
            ('I03', 'Equipo de transporte.'),
            ('I04', 'Equipo de computo y accesorios.'),
            ('I05', 'Dados, troqueles, moldes, matrices y herramental.'),
            ('I06', 'Comunicaciones telefónicas.'),
            ('I07', 'Comunicaciones satelitales.'),
            ('I08', 'Otra maquinaria y equipo.'),
            ('D01', 'Honorarios médicos, dentales y gastos hospitalarios.'),
            ('D02', 'Gastos médicos por incapacidad o discapacidad.'),
            ('D03', 'Gastos funerales.'),
            ('D04', 'Donativos.'),
            ('D05', 'Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación).'),
            ('D06', 'Aportaciones voluntarias al SAR.'),
            ('D07', 'Primas por seguros de gastos médicos.'),
            ('D08', 'Gastos de transportación escolar obligatoria.'),
            ('D09', 'Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones.'),
            ('D10', 'Pagos por servicios educativos (colegiaturas).'),
            ('S01', 'Sin efectos fiscales.'),
            ('P01', 'Por definir'),
            ('CP01', 'Pagos'),
            ('CN01', 'Nómina'),
        ],
        string="Uso")

    l10n_mx_edi_payment_method_id = fields.Many2one('l10n_mx_edi.payment.method',
        string="Forma de pago",)

