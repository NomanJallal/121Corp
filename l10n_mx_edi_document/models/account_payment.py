# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, models
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def xml2record(self):
        """Use the last attachment in the payment (xml) and fill the payment
        data"""
        atts = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids),
        ])
        avoid_create = self.env['ir.config_parameter'].sudo().get_param(
            'mexico_document_avoid_create_payment')
        incorrect_folder = self.env.ref(
            'l10n_mx_edi_document.documents_cfdi_not_found_folder', False)
        rule_tc = self.env.ref('documents.documents_rule_finance_validate')
        for attachment in atts:
            cfdi = attachment.l10n_mx_edi_is_cfdi33()
            if cfdi is False:
                continue
            amount = 0
            currency = self.env['res.currency']
            invoices = self.env['account.move']
            for elem in self.l10n_mx_edi_get_payment_etree(cfdi):
                parent = elem.getparent()
                if not amount:
                    amount += float(parent.get('Monto'))
                payment_method = self.env['l10n_mx_edi.payment.method'].search(
                    [('code', '=', parent.get('FormaDePagoP'))], limit=1)
                currency = currency.search([
                    ('name', '=', parent.get('MonedaP'))], limit=1)
                invoices |= invoices.search([
                    ('l10n_mx_edi_cfdi_uuid', '=', elem.get('IdDocumento').upper().strip())])
            document_type, _res_model = attachment.l10n_edi_document_type()
            payment_data = {
                'amount': amount,
                'l10n_mx_edi_payment_method_id': payment_method.id,
                'date': cfdi.get('Fecha').split('T')[0],
                'l10n_mx_edi_post_time': cfdi.get('Fecha').replace('T', ' '),
                'currency_id': currency.id,
                'uuid': self.move_id._l10n_mx_edi_decode_cfdi().get('uuid'),
                'payment_type': 'inbound' if document_type == 'customerP' else 'outbound',
            }
            payment_match = self.l10n_mx_edi_payment_match(
                payment_data, invoices)
            if payment_match:
                payment_match.edi_state = 'sent'
                if not payment_match.edi_document_ids:
                    self.env['account.edi.document'].create({
                        'edi_format_id': self.env.ref('l10n_mx_edi.edi_cfdi_3_3').id,
                        'move_id': payment_match.move_id.id,
                        'state': 'sent',
                        'attachment_id': attachment.id,
                    })
                return payment_match
            if avoid_create:
                attachment.res_model = False
                attachment.res_id = False
                documents = self.env['documents.document'].search([('attachment_id', 'in', attachment.ids)])
                rule_tc.apply_actions(documents.ids)
                documents.folder_id = incorrect_folder
                self.unlink()
                continue
            self.l10n_mx_edi_set_cfdi_partner(
                cfdi, currency, 'inbound' if document_type == 'customerP' else 'outbound')
            del payment_data['uuid']
            self.write(payment_data)
            self.edi_state = 'sent'
            self.action_post()
            self.env['account.edi.document'].create({
                'edi_format_id': self.env.ref('l10n_mx_edi.edi_cfdi_3_3').id,
                'move_id': self.move_id.id,
                'state': 'sent',
                'attachment_id': attachment.id,
            })
            move = self.move_id.line_ids.filtered(
                lambda line: line.account_id.internal_type in ('receivable', 'payable'))
            for inv in invoices:
                lines = move
                lines |= inv.line_ids.filtered(
                    lambda line: line.account_id in lines.mapped('account_id') and
                    not line.reconciled)
                lines.reconcile()
            attachment.copy({'res_model': 'account.move', 'res_id': self.move_id.id, 'mimetype': 'application/xml'})
        return self.exists()

    def l10n_mx_edi_payment_match(self, payment_data, invoices):
        """Search a payment with the same data that payment_data and merge with
        it, to avoid 2 payments with the same data."""
        payments = [payment._get_reconciled_info_JSON_values()
                    for payment in invoices]
        payments = [payment[0].get(
            'account_payment_id') for payment in payments if payment]
        payments = self.search([('id', 'in', payments)])
        for payment in payments:
            uuid = not payment.l10n_mx_edi_cfdi_uuid or payment_data.get('uuid') == payment.l10n_mx_edi_cfdi_uuid
            if float_compare(payment_data['amount'], payment.amount, precision_digits=0) == 0 and uuid:  # noqa
                payment.message_post(body=_(
                    'The CFDI attached to was assigned with DMS.'))
                self.env['ir.attachment'].search([
                    ('res_id', '=', self.id),
                    ('res_model', '=', self._name)]).res_id = payment.id
                self.unlink()
                return payment
        return False

    def l10n_mx_edi_set_cfdi_partner(self, cfdi, currency, payment_type):
        # TODO - make method generic
        self.ensure_one()
        partner = self.env['res.partner']
        domain = []
        partner_cfdi = {}
        if payment_type == 'inbound':
            partner_cfdi = cfdi.Receptor
            domain.append(('vat', '=', partner_cfdi.get('Rfc')))
        elif payment_type == 'outbound':
            partner_cfdi = cfdi.Emisor
            domain.append(('vat', '=', partner_cfdi.get('Rfc')))
        domain.append(('is_company', '=', True))
        cfdi_partner = partner.search(domain, limit=1)
        currency_field = 'property_purchase_currency_id' in partner._fields
        if currency_field:
            domain.append(('property_purchase_currency_id', '=', currency.id))
        if currency_field and not cfdi_partner:
            domain.pop()
            cfdi_partner = partner.search(domain, limit=1)
        if not cfdi_partner:
            domain.pop()
            cfdi_partner = partner.search(domain, limit=1)
        if not cfdi_partner:
            domain.pop()
            cfdi_partner = partner.search(domain, limit=1)
        if not cfdi_partner:
            cfdi_partner = partner.create({
                'name': partner_cfdi.get('Nombre'),
                'vat': partner_cfdi.get('Rfc'),
                'country_id': False,  # TODO
            })
            cfdi_partner.message_post(body=_(
                'This record was generated from DMS'))
        self.partner_id = cfdi_partner

    @api.model
    def l10n_mx_edi_get_payment_etree(self, cfdi):
        """Get the Complement node from the cfdi.
        """
        # TODO: Remove this method
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = '//pago10:DoctoRelacionado'
        namespace = {'pago10': 'http://www.sat.gob.mx/Pagos'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node

    def _get_edi_document_errors(self):
        errors = []
        if self.country_code != 'MX':
            return errors
        if not self.company_id.l10n_mx_edi_pac_test_env and self.l10n_mx_edi_sat_status != 'valid':
            errors.append(
                'The SAT status of this document is not valid in the SAT. (Is %s)' % self.l10n_mx_edi_sat_status)
        return errors
