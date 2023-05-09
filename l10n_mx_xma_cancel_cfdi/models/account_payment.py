
import base64
from itertools import groupby
import re
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from io import BytesIO
import requests
from pytz import timezone

from lxml import etree
from lxml.objectify import fromstring
from zeep import Client
from zeep.transports import Transport

from odoo import _, api, fields, models, tools
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr

from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit

import logging
_logger = logging.getLogger(__name__)



class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_mx_xma_cfdi_cancel_to_cancel = fields.Boolean(
        string='Documento a cancelar',
        copy=False,
        default=False,
    )
    l10n_mx_xma_cfdi_cancel_cancel_type_id = fields.Many2one(
        'edi.mx.cancel.motive',
        string='Motivo de cancelación',
        copy=False,
        domain=[('is_to_payment','=',True)]
    )


    def button_l10n_mx_xma_cfdi_is_to_cance(self):
        for rec in self:
            rec.l10n_mx_xma_cfdi_cancel_to_cancel = True


    def button_l10n_mx_xma_cfdi_cancel_request_cancel(self):
        for rec in self:
            if rec.l10n_mx_xma_cfdi_cancel_cancel_type_id:
                if rec.l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code == '01':
                    count = self.env['account.payment'].search_count([('replace_uuid', '=', rec.replace_uuid)])
                    print("count",count)
                    if count > 1:
                        raise UserError("No se puede usar este motivo decancelación ya que no existe un documento previo.")
                   

                # elif rec.l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code == '02':
                #     if rec.amount_total != rec.amount_residual:
                #         raise UserError("El CFDI cuenta con documentos relacionados, no debería utilizar este motivo de cancelación.")
            else:
                raise UserError("Es necesario establecer un motivo de cancelación")
            pac_info = rec.cancel_pac_info()
            rec.l10n_mx_edi_finkok_cancel(pac_info)
            rec.write({'state':'cancelled'})

    def cancel_pac_info(self):
        for rec in self:
            service_type = "cancel"
            invoice_obj = self.env['account.move']
            # Regroup the invoices by company (= by pac)
            comp_x_records = groupby(self, lambda r: r.company_id)
            for company_id, records in comp_x_records:
                pac_name = company_id.l10n_mx_edi_pac
                if not pac_name:
                    continue
                # Get the informations about the pac
                pac_info_func = '_l10n_mx_edi_%s_info' % pac_name
                service_func = '_l10n_mx_edi_%s_%s' % (pac_name, service_type)
                pac_info = getattr(invoice_obj, pac_info_func)(company_id, service_type)
                return pac_info


    replace_uuid = fields.Char(string="Reemplazar Folio Fiscal", copy=False)

    code_motive = fields.Char(
        string='Code',
        related="l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code",
        store=True,
        copy=False,

    )


    def l10n_mx_edi_finkok_cancel(self, pac_info):
        '''CANCEL for Finkok.
        '''
        _logger.info("VALORESSSSSSSSSSSS  pac_info <%s>", pac_info)
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for inv in self:
            uuid = inv.l10n_mx_edi_cfdi_uuid
            certificate_ids = inv.company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            company_id = self.company_id
            cer_pem = certificate_id.get_pem_cer(certificate_id.content)
            key_pem = certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)
            cancelled = False
            code = False
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                # uuid_type = client.get_type('ns0:stringArray')()
                # uuid_type.string = [uuid]
                # invoices_list = client.get_type('ns1:UUIDS')(uuid_type)
                ###########
                uuid_type = client.get_type('ns1:UUID')()
                uuid_type.UUID = uuid
                uuid_type.FolioSustitucion = inv.replace_uuid or ''
                if not inv.l10n_mx_xma_cfdi_cancel_cancel_type_id:
                    raise UserError("reason not defined")
                uuid_type.Motivo = inv.l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code
                invoices_list = client.get_type('ns1:UUIDS')(uuid_type)
                #############
                response = client.service.cancel(invoices_list, username, password, company_id.vat, cer_pem, key_pem)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                continue
            if not (hasattr(response, 'Folios') and response.Folios):
                msg = _('A delay of 2 hours has to be respected before to cancel')
            else:
                code = getattr(response.Folios.Folio[0], 'EstatusUUID', None)
                cancelled = code in ('201', '202')  # cancelled or previously cancelled
                # no show code and response message if cancel was success
                code = '' if cancelled else code
                msg = '' if cancelled else _("Cancelling got an error")
            inv._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

   