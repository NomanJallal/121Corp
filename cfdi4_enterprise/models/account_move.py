# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_repr
from io import BytesIO
import xmlrpc.client
import base64
import requests

from lxml import etree
from lxml.objectify import fromstring
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools.xml_utils import _check_with_xsd
from pytz import timezone
from datetime import datetime
from dateutil.relativedelta import relativedelta

CFDI_TEMPLATE_33 = 'cfdi4_enterprise.cfdiv40'
CFDI_XSLT_CADENA = 'cfdi4_enterprise/data/%s/cadenaoriginal.xslt'
CFDI_XSLT_CADENA_TFD = 'cfdi4_enterprise/data/xslt/4.0/cadenaoriginal_TFD_1_1.xslt'


import logging
_logger = logging.getLogger(__name__)


def create_list_html(array):
    '''Convert an array of string to a html list.
    :param array: A list of strings
    :return: an empty string if not array, an html list otherwise.
    '''
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'


class AccountMove(models.Model):
    _inherit = "account.move"

    

    def _l10n_mx_edi_get_payment_policy(self):
        self.ensure_one()
        version = self.l10n_mx_edi_get_pac_version()
        term_ids = self.invoice_payment_term_id.line_ids
        if version == '3.2':
            if len(term_ids.ids) > 1:
                return 'Pago en parcialidades'
            else:
                return 'Pago en una sola exhibición'
        elif version in ('3.3', '4.0') and self.invoice_date_due and self.invoice_date:
            if self.type == 'out_refund':
                return 'PUE'
            # In CFDI 3.3 - rule 2.7.1.43 which establish that
            # invoice payment term should be PPD as soon as the due date
            # is after the last day of  the month (the month of the invoice date).
            if self.invoice_date_due.month > self.invoice_date.month or \
                    self.invoice_date_due.year > self.invoice_date.year or \
                    len(term_ids) > 1:  # to be able to force PPD
                return 'PPD'
            return 'PUE'
        return ''

    @api.model
    def l10n_mx_edi_get_pac_version(self):
        '''Returns the cfdi version to generate the CFDI.
        In December, 1, 2017 the CFDI 3.2 is deprecated, after of July 1, 2018
        the CFDI 3.3 could be used.
        '''

        return '4.0'

    def _l10n_mx_edi_create_cfdi(self):
        '''Creates and returns a dictionnary containing 'cfdi' if the cfdi is well created, 'error' otherwise.
        '''
        self.ensure_one()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        pac_name = company_id.l10n_mx_edi_pac
        if self.l10n_mx_edi_external_trade:
            # Call the onchange to obtain the values of l10n_mx_edi_qty_umt
            # and l10n_mx_edi_price_unit_umt, this is necessary when the
            # invoice is created from the sales order or from the picking
            self.invoice_line_ids.onchange_quantity()
            self.invoice_line_ids._set_price_unit_umt()
        values = self._l10n_mx_edi_create_cfdi_values()

        # -----------------------
        # Check the configuration
        # -----------------------
        # -Check certificate
        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        if not certificate_id:
            error_log.append(_('No valid certificate found'))

        # -Check PAC
        if pac_name:
            pac_test_env = company_id.l10n_mx_edi_pac_test_env
            pac_password = company_id.l10n_mx_edi_pac_password
            if not pac_test_env and not pac_password:
                error_log.append(_('No PAC credentials specified.'))
        else:
            error_log.append(_('No PAC specified.'))

        if error_log:
            return {'error': _('Please check your configuration: ') + create_list_html(error_log)}

        # -Compute date and time of the invoice
        time_invoice = datetime.strptime(self.l10n_mx_edi_time_invoice,
                                         DEFAULT_SERVER_TIME_FORMAT).time()
        # -----------------------
        # Create the EDI document
        # -----------------------
        version = self.l10n_mx_edi_get_pac_version()

        # -Compute certificate data
        values['date'] = datetime.combine(
            fields.Datetime.from_string(self.invoice_date), time_invoice).strftime('%Y-%m-%dT%H:%M:%S')
        values['certificate_number'] = certificate_id.serial_number
        values['certificate'] = certificate_id.sudo().get_data()[0]

        # -Compute cfdi
        cfdi = qweb.render(CFDI_TEMPLATE_33, values=values)
        cfdi = cfdi.replace(b'xmlns__', b'xmlns:')
        node_sello = 'Sello'
        attachment = self.sudo().env.ref('cfdi4_enterprise.xsd_cached_cfdv40_xsd', False)
        xsd_datas = base64.b64decode(attachment.datas) if attachment else b''

        # -Compute cadena
        tree = self.l10n_mx_edi_get_xml_etree(cfdi)
        print("xxxxx",CFDI_XSLT_CADENA,version,tree)
        cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA % version, tree)
        tree.attrib[node_sello] = certificate_id.sudo().get_encrypted_cadena(cadena)

        # Check with xsd
        if xsd_datas:
            try:
                with BytesIO(xsd_datas) as xsd:
                    _check_with_xsd(tree, xsd)
            except (IOError, ValueError):
                _logger.info(
                    _('The xsd file to validate the XML structure was not found'))
            except Exception as e:
                return {'error': (_('The cfdi generated is not valid') +
                                  create_list_html(str(e).split('\\n')))}

        return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}

    @api.model
    def _get_l10n_mx_edi_cadena(self):
        self.ensure_one()
        # get the xslt path
        xslt_path = CFDI_XSLT_CADENA_TFD
        # get the cfdi as eTree
        cfdi = base64.decodebytes(self.l10n_mx_edi_cfdi)
        cfdi = self.l10n_mx_edi_get_xml_etree(cfdi)
        cfdi = self.l10n_mx_edi_get_tfd_etree(cfdi)
        # return the cadena
        return self.l10n_mx_edi_generate_cadena(xslt_path, cfdi)

    def get_new_cfdi_fields(self, name):
        if name == 'Exportacion':
            return "01"
        if name == 'FacAtrAdquirente':
            return False

    def show(self, line):
        return 0


    def account_move_values(self,ids):
        account = self.env["account.move"].search([('id', '=', ids)], limit=1)        
        return account

    def account_move_tax(self,ids):
        tax = self.env["account.tax"].search([('tax_group_id', '=', ids),('type_tax_use', '=', 'sale')], limit=1)        
        return tax

    def account_move_ObjetoImpDR(self,vals):
        imp = 0
        
        if int(vals['ivatra08']) > 0:
            imp += 1
        if int(vals['ivatra16']) > 0:
            imp += 1
        if int(vals['retiva'] * -1) > 0:
            imp += 1
        if int(vals['retisr'] * -1) > 0:
            imp += 1
        if imp >= 1:
            return '02'
        else:
            return '01'


    def account_move_tax_totals(self,invoice,currency):
        retiva = 0
        retisr = 0
        ivabase16 = 0
        ivatra16 = 0
        ivabase08 = 0
        ivatra08 = 0
        for rec in invoice:
            for inv in rec['invoice']:
                for tax in inv.amount_by_group:
                    if tax[0] == "IVA 16%":
                        ivabase16 += tax[2]
                        ivatra16 += tax[1]
                    if tax[0] == "IVA Retencion 10.67%":
                        retiva += tax[1]
                    if tax[0] == "ISR Retencion 10%":
                        retisr += tax[1]

                    if tax[0] == "IVA 8%":
                        ivabase08 += tax[2]
                        ivatra08 += tax[1]

        if self.currency_id.name == 'MXN':

            vals = {
                'ivabase08':ivabase08,
                'ivatra08':ivatra08,
                'ivabase16':ivabase16,
                'ivatra16':ivatra16,
                'retiva': retiva,
                'retisr': retisr,
            }
        else:
            vals = {
                'ivabase08': round(float(ivabase08) / float(currency),2),
                'ivatra08':round(float(ivatra08) / float(currency),2),
                'ivabase16': round(float(ivabase16) / float(currency),2),
                'ivatra16':round(float(ivatra16) / float(currency),2),
                'retiva': round(float(retiva) / float(currency),2),
                'retisr': round(float(retisr) / float(currency),2),
            }
                                        
        return vals

    l10n_mx_edi_usage = fields.Selection(
        selection_add=[
            ('S01', 'Sin efectos fiscales.'),
            ('CP01', 'Pagos'),
            ('CN01', 'Nómina'),
        ])


    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id.l10n_mx_edi_usage:
            self.l10n_mx_edi_usage = self.partner_id.l10n_mx_edi_usage
        else:
            self.l10n_mx_edi_usage = ''
        if self.partner_id.l10n_mx_edi_payment_method_id:
            self.write({'l10n_mx_edi_payment_method_id':self.partner_id.l10n_mx_edi_payment_method_id.id })
        else:
            self.write({'l10n_mx_edi_payment_method_id':False})
        return super(AccountMove, self)._onchange_partner_id()

    def xxxx(self,v):
        print("xxxxx 1 xxxxxxx",v)

        vv=v.filtered('price_subtotal').tax_ids.flatten_taxes_hierarchy()

        vvv = vv.filtered(lambda r: r.amount >= 0)
        b = tax_line.get(tax.id, {})
        vvvv =  abs(tax_dict.get('amount', (tax.amount if tax.amount_type == 'fixed' else tax.amount / 100.0) * line.price_subtotal))
        print("+++++++++++",vv,vvv)



    def xxx(self,v,vv,vvv):
        print("xxxxxx 2 xxxxxx",v,vv,vvv)

        