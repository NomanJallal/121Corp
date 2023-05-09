
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



class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_mx_xma_cfdi_cancel_to_cancel = fields.Boolean(
        string='Documento a cancelar',
        copy=False,
        default=False,
    )
    l10n_mx_xma_cfdi_cancel_cancel_type_id = fields.Many2one(
        'edi.mx.cancel.motive',
        string='Motivo de cancelación',
        copy=False,
    )
    global_invoice = fields.Boolean(
        string='Factura global',
    )


    def button_l10n_mx_xma_cfdi_is_to_cance(self):
        for rec in self:
            rec.l10n_mx_xma_cfdi_cancel_to_cancel = True


    def button_l10n_mx_xma_cfdi_cancel_request_cancel(self):
        for rec in self:
            if rec.l10n_mx_xma_cfdi_cancel_cancel_type_id:
                if rec.l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code == '01':
                    if rec.amount_total == rec.amount_residual:
                        count = self.env['account.move'].search_count([('replace_uuid', '=', rec.replace_uuid)])
                        print("count",count)
                        if count > 1:
                            raise UserError("No se puede usar este motivo decancelación ya que no existe un documento previo.")
                    else:                        
                        raise UserError("El CFDI cuenta con documentos relacionados, se tienen que cancelar primero los movimientos dependientes.")

                elif rec.l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code == '02':
                    if rec.amount_total != rec.amount_residual:
                        raise UserError("El CFDI cuenta con documentos relacionados, no debería utilizar este motivo de cancelación.")
                elif rec.l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code == '03':
                    if rec.amount_total != rec.amount_residual:
                        raise UserError("El CFDI cuenta con documentos relacionados, no debería utilizar este motivo de cancelación.")
                elif rec.l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code == '04':
                    if rec.global_invoice == False:
                        raise UserError("No es una factura global por lo que no puede usar este motivo de cancelación")
                    else:
                        if rec.partner_id.vat != 'XAXX010101000':
                            raise UserError("El RFC no corresponde a XAXX010101000 necesario para la factura global")


            else:
                raise UserError("Es necesario establecer un motivo de cancelación")

            pac_info = rec.cancel_pac_info()
            _logger.info("VALORESSSSSSSSSSSS  pac_info <%s>", pac_info)
            rec.l10n_mx_edi_finkok_cancel(pac_info)
            

    def cancel_pac_info(self):
        for rec in self:
            service_type = "cancel"
            comp_x_records = groupby(self, lambda r: r.company_id)
            for company_id, records in comp_x_records:
                pac_name = company_id.l10n_mx_edi_pac
                if not pac_name:
                    continue
                # Get the informations about the pac
                pac_info_func = '_l10n_mx_edi_%s_info' % pac_name
                service_func = '_l10n_mx_edi_%s_%s' % (pac_name, service_type)
                pac_info = getattr(self, pac_info_func)(company_id, service_type)
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
        _logger.info("VALORESSSSSSSSSSSS  inv.l10n_mx_xma_cfdi_cancel_cancel_type_id.code <%s>", self.l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code)
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for inv in self:
            uuid = inv.l10n_mx_edi_cfdi_uuid
            certificate_ids = inv.company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            company_id = self.company_id
            cer_pem = certificate_id.get_pem_cer(
                certificate_id.content)
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
                #####################################
                uuid_type = client.get_type('ns1:UUID')()
                uuid_type.UUID = uuid
                uuid_type.FolioSustitucion = inv.replace_uuid or ''
                if not inv.l10n_mx_xma_cfdi_cancel_cancel_type_id:
                    raise UserError("reason not defined")
                uuid_type.Motivo = inv.l10n_mx_xma_cfdi_cancel_cancel_type_id.default_code
                invoices_list = client.get_type('ns1:UUIDS')(uuid_type)
                _logger.info("VALORESSSSSSSSSSSS  uuid_type <%s>", uuid_type)
                                       
                #####################################
                _logger.info("VALORESSSSSSSSSSSS  invoices_list <%s> username <%s> password <%s> company_id.vat <%s> cer_pem <%s> key_pem <%s> ", invoices_list, username, password, company_id.vat, cer_pem, key_pem)
                response = client.service.cancel(
                    invoices_list, username, password, company_id.vat, cer_pem, key_pem)
                _logger.info("VALORESSSSSSSSSSSS  response <%s>", response)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                continue
            if not getattr(response, 'Folios', None):
                code = getattr(response, 'CodEstatus', None)
                msg = _("Cancelling got an error") if code else _(
                    'A delay of 2 hours has to be respected before to cancel')
            else:
                code = getattr(response.Folios.Folio[0], 'EstatusUUID', None)
                cancelled = code in ('201', '202')  # cancelled or previously cancelled
                # no show code and response message if cancel was success
                code = '' if cancelled else code
                msg = '' if cancelled else _("Cancelling got an error")
            inv._l10n_mx_edi_post_cancel_process(cancelled, code, msg)
        #raise UserError(_("xxxxx"))


    def l10n_mx_edi_update_sat_status(self):
        for inv in self.filtered('l10n_mx_edi_cfdi'):
            supplier_rfc = inv.l10n_mx_edi_cfdi_supplier_rfc
            customer_rfc = inv.l10n_mx_edi_cfdi_customer_rfc
            total = float_repr(inv.l10n_mx_edi_cfdi_amount,
                               precision_digits=inv.currency_id.decimal_places)
            uuid = inv.l10n_mx_edi_cfdi_uuid

            status = inv._l10n_mx_edi_get_sat_status(supplier_rfc, customer_rfc, total, uuid)
            if status.startswith('error'):
                inv.l10n_mx_edi_log_error(status)
                continue
            inv.l10n_mx_edi_sat_status = status
            if inv.l10n_mx_edi_sat_status == 'cancelled':
                rec.write({'state':'cancel'})