# Copyright 2020, Vauxoo, S.A. de C.V.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import base64
import logging
from io import BytesIO

from lxml import objectify, etree
from odoo import api, models, _
from odoo.tools.xml_utils import _check_with_xsd
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def l10n_mx_edi_is_cfdi33(self):
        self.ensure_one()
        if not self.datas:
            return False
        try:
            datas = base64.b64decode(self.datas).replace(
                b'xmlns:schemaLocation', b'xsi:schemaLocation').replace(b'data:text/xml;base64,', b'').replace(
                    b'o;?', b'').replace(b'\xef\xbf\xbd', b'')
            self.datas = base64.b64encode(datas)
            cfdi = objectify.fromstring(datas)
        except (SyntaxError, ValueError):
            return False
        version = cfdi.get('Version')
        if version not in ['3.3', '4.0']:
            return None
        attachment = self.sudo().env.ref('l10n_mx_edi.xsd_cached_cfdv33_xsd', False) if version == '3.3' else False
        try:
            schema = base64.b64decode(attachment.datas) if attachment else b''
            if not hasattr(cfdi, 'Complemento'):
                return False
            if hasattr(cfdi, 'Addenda'):
                cfdi.remove(cfdi.Addenda)
            if not attachment:
                return cfdi
            attribute = 'registrofiscal:CFDIRegistroFiscal'
            namespace = {'registrofiscal': 'http://www.sat.gob.mx/registrofiscal'}
            node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
            if node:
                cfdi.Complemento.remove(node[0])
            with BytesIO(schema) as xsd:
                _check_with_xsd(cfdi, xsd)
            return cfdi
        except (ValueError, IOError, UserError, etree.XMLSyntaxError):
            return False
        return False

    def l10n_edi_document_type(self, document=False):
        self.ensure_one()
        company = document.company_id or self.company_id if document else self.company_id
        if company.country_code != 'MX':
            return super().l10n_edi_document_type(document=document)
        cfdi = self.l10n_mx_edi_is_cfdi33()
        if cfdi is False:
            return False, {'error': 'This Document is not a CFDI valid.'}
        res_model = {
            'P': 'account.payment',
            'I': 'account.move',
            'E': 'account.move',
        }.get(cfdi.get('TipoDeComprobante'))
        document_type = 'customer' if cfdi.Emisor.get('Rfc') == company.vat else (
            'vendor' if cfdi.Receptor.get('Rfc') == company.vat else False)
        if not document_type:
            return False, {'error': _(
                'Neither the emitter nor the receiver of this CFDI is this company, please review this document.')}
        return [('%s%s' % (document_type, cfdi.get('TipoDeComprobante'))) if document_type else False, res_model]
