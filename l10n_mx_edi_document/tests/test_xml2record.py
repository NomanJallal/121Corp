# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import os
from os.path import join
from lxml import etree
from lxml.objectify import fromstring
from odoo.tools import misc
from odoo.tools.float_utils import float_compare

from odoo.tests.common import Form
from odoo.tests.common import TransactionCase


class Xml2Record(TransactionCase):

    def setUp(self):
        super().setUp()
        self.rule = self.env.ref('l10n_edi_document.edi_document_rule')
        self.invoice_xml = misc.file_open(join('l10n_mx_edi_document', 'tests', 'invoice.xml')).read().encode('UTF-8')
        self.payment_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'payment.xml')).read().encode(
                'UTF-8')
        self.finance_folder = self.env.ref(
            'documents.documents_finance_folder')
        self.env.ref('product.product_product_4d').unspsc_code_id = self.env.ref(
            'product_unspsc.unspsc_code_01010101')
        self.env['l10n_mx_edi.certificate'].search([]).unlink()
        self.certificate = self.env['l10n_mx_edi.certificate'].create({
            'content': base64.encodebytes(misc.file_open(os.path.join(
                'l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.cer'), 'rb').read()),
            'key': base64.encodebytes(misc.file_open(os.path.join(
                'l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.key'), 'rb').read()),
            'password': '12345678a',
        })
        self.certificate._check_credentials()
        company_values = {
            'vat': 'EKU9003173C9',
            'zip': '85134',
            'city': 'Ciudad Obregón',
            'country_id': self.env.ref('base.mx').id,
            'state_id': self.env.ref('base.state_mx_son').id,
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
            'l10n_mx_edi_fiscal_regime': '601',
            'l10n_mx_edi_certificate_ids': [(6, 0, self.certificate.ids)],

        }
        self.env.user.company_id.write(company_values)

    def test_invoice_payment(self):
        """The invoice must be generated based in the payment, after the
        payment must be reconciled with the invoice"""
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        attachment = attachment.create({
            'name': 'payment.xml',
            'datas': base64.b64encode(self.payment_xml),
            'description': 'Mexican payment',
        })
        payment_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        self.rule.create_record(payment_document)
        self.assertEqual(
            self.env['account.move'].browse(invoice).payment_state, 'paid', 'Invoice was not paid')

    def test_payment_existent(self):
        """If the payment is found, not must be created a new."""
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        invoice = self.env['account.move'].browse(invoice)
        self.assertEqual(invoice.edi_state, 'sent', invoice.message_ids.mapped('body'))

        self.bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank')], limit=1)
        invoice.refresh()
        payment_register = Form(self.env['account.payment'].with_context(
            active_model='account.move', active_ids=invoice.ids, default_date=invoice.invoice_date))
        payment_register.journal_id = self.bank_journal
        payment_register.amount = invoice.amount_total
        payment_register.partner_id = invoice.partner_id
        payment = payment_register.save()
        payment.action_post()
        payment_method_manual = self.env.ref("account.account_payment_method_manual_in")
        self.assertEqual(payment_method_manual.id, payment.payment_method_id.id)
        lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id.internal_type in ('receivable', 'payable'))
        lines |= invoice.line_ids.filtered(
            lambda line: line.account_id in lines.mapped('account_id') and not line.reconciled)
        lines.reconcile()
        attachment = attachment.create({
            'name': 'payment.xml',
            'datas': base64.b64encode(self.payment_xml),
            'description': 'Mexican payment',
        })
        payment_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        new_payment = self.rule.create_record(payment_document).get('res_id')
        self.assertEqual(
            payment.id, new_payment,
            'A new payment was created, that is incorrect')

    def _test_payment_not_existent(self):
        """2 payments created."""
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        attachment = attachment.create({
            'name': 'payment.xml',
            'datas': base64.b64encode(self.payment_xml),
            'description': 'Mexican payment',
        })
        payment_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        payment = self.rule.create_record(payment_document).get('res_id')
        self.env['account.payment'].browse(payment).refresh()
        new_xml = self.payment_xml.replace(b'UUID="0', b'UUID="1')
        attachment = attachment.create({
            'name': 'payment.xml',
            'datas': base64.b64encode(new_xml),
            'description': 'Mexican payment',
        })
        payment_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        new_payment = self.rule.create_record(payment_document).get('res_id')
        self.assertNotEqual(payment, new_payment, 'Both payments are the same')
        self.assertEqual(
            self.env['account.move'].browse(invoice).payment_state, 'paid', 'Invoice was not paid')

    def test_payment_not_created(self):
        """Avoid payment creation."""
        self.env['ir.config_parameter'].create({
            'key': 'mexico_document_avoid_create_payment',
            'value': True})
        attachment = self.env['ir.attachment'].create({
            'name': 'payment.xml',
            'datas': base64.b64encode(self.payment_xml),
            'store_fname': 'payment.xml',
            'description': 'Mexican payment',
        })
        payment_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        payment = self.rule.create_record(payment_document).get('res_id')
        self.assertFalse(
            payment, 'The payment was created with the system parameter')

    def test_invoice_duplicated(self):
        """The invoice must be generated only one time"""
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = invoice_document.copy({
            'attachment_id': attachment.id
        })
        invoice2 = self.rule.create_record(invoice_document).get('res_id')
        self.assertEqual(invoice, invoice2, 'Invoice generated 2 times.')

    def test_invoice_withholding(self):
        """The invoice must be generated with withholding tax"""
        self.invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'data', 'cfdi_withholding.xml')).read().encode('UTF-8')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        self.assertTrue(self.rule.create_record(invoice_document).get('res_id'), 'Invoice not generated.')

    def test_invoice_local_taxes(self):
        """The invoice must be generated with local taxes."""
        self.invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'data', 'cfdi_imp_local.xml')).read().encode('UTF-8')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        self.assertTrue(invoice, 'Invoice not generated.')
        invoice = self.env['account.move'].browse(invoice)
        self.assertEqual(invoice.amount_total, float(fromstring(self.invoice_xml).get('Total')),
                         'Local Tax not added correctly.')

    def test_invoice_fuel(self):
        """The invoice must be generated correctly with fuel products."""
        self.invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'data', 'cfdi_fuel.xml')).read().encode('UTF-8')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        self.assertTrue(invoice, 'Invoice not generated.')
        invoice = self.env['account.move'].browse(invoice)
        self.assertEqual(
            float_compare(invoice.amount_total, float(fromstring(self.invoice_xml).get('Total')), precision_digits=0),
            0, 'FUEL test is failing.')

    def test_4_decimals(self):
        """Test with decimal places in 4"""
        self.env.ref('base.MXN').write({'rounding': 0.000100})
        self.invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'invoice_decimals.xml')).read().encode('UTF-8')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        self.assertTrue(invoice, 'Invoice not generated')

    def test_custom_fields(self):
        self.invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'vendor_bill.xml')).read().encode('UTF-8')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        journal = self.env['account.journal'].search([('type', '=', 'purchase')], limit=1)
        account = journal.default_account_id.copy({'name': 'Account Test'})
        journal = journal.copy({'name': 'Journal Test'})
        date = self.env['l10n_mx_edi.certificate'].get_mx_current_datetime()
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id,
            'vendor_journal_id': journal.id,
            'vendor_account_id': account.id,
            'invoice_date': date,
            'analytic_account_id': self.env.ref('analytic.analytic_administratif').id,
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        invoice = self.env['account.move'].browse(invoice)
        self.assertEqual(invoice.journal_id, journal, 'Journal not comes from document.')
        self.assertEqual(invoice.invoice_line_ids.filtered(
            lambda l: not l.product_id).account_id, account, 'Account not comes from document.')
        self.assertEqual(invoice.invoice_date, date.date(), 'Date not comes from document.')
        self.assertTrue(invoice.invoice_line_ids.mapped('analytic_account_id'), 'Analytic account not assigned.')

    def test_same_emitter_receiver(self):
        """Ensure that if the receiver is the same that the emitter, the CFDI is attached in a supplier invoice"""
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id,
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        invoice = self.env['account.move'].browse(invoice)

        # Update company data to CFDI 4.0
        invoice.company_id.sudo().search([('name', '=', 'ESCUELA KEMPER URGATE')]).write({'name': 'ESCUELA'})
        invoice.company_id.name = 'ESCUELA KEMPER URGATE'
        invoice.company_id.partner_id.zip = '20928'
        invoice.company_id.partner_id.l10n_mx_edi_fiscal_regime = '601'

        invoice = invoice.copy({'partner_id': invoice.company_id.partner_id.id, })
        self.env.user.company_id.sudo().search([('name', '=', 'ESCUELA KEMPER URGATE')]).name = 'ESCUELA KEMPER'
        invoice.partner_id.name = 'ESCUELA KEMPER URGATE'
        invoice.partner_id.l10n_mx_edi_fiscal_regime = '601'
        invoice.partner_id.zip = 20928
        move_form = Form(invoice)
        product = invoice.invoice_line_ids.mapped('product_id')
        with move_form.invoice_line_ids.edit(1) as line_form:
            line_form.product_id = product
        move_form.save()
        invoice.journal_id.edi_format_ids = [(6, 0, self.env.ref('l10n_mx_edi.edi_cfdi_3_3').ids)]
        invoice.action_post()
        invoice.action_process_edi_web_services()
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_document_ids.error)
        attachment = invoice.edi_document_ids.attachment_id.copy({
            'res_model': 'document.document',
            'res_id': False,
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id,
        })
        bill = self.rule.create_record(invoice_document).get('res_id')
        self.assertNotEqual(invoice.id, bill, 'Invoice and Bill are the same.')

    def test_not_serie_folio(self):
        """Ensure that invoice is not duplicated if serie and folio is not set"""
        xml = fromstring(self.invoice_xml)
        xml.attrib.pop('Folio')
        xml.attrib.pop('Serie')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(etree.tostring(xml)),
            'description': 'Mexican invoice',
        })
        attachment2 = attachment.copy()
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        invoice_document = invoice_document.copy({
            'attachment_id': attachment2.id
        })
        invoice2 = self.rule.create_record(invoice_document).get('res_id')
        self.assertEqual(invoice, invoice2, 'Invoice generated 2 times.')

        # Update date in the CFDI
        self.env['ir.config_parameter'].create({'key': 'documents_force_use_date', 'value': 'month'})
        xml.attrib.update({'Fecha': '2019-10-24T14:17:06'})
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        xml.Complemento.xpath(attribute, namespaces=namespace)[0].attrib.update(
            {'UUID': '2BFDB74F-DC70-4274-972D-6F7B53E182F5'})
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(etree.tostring(xml)),
            'description': 'Mexican invoice',
        })
        invoice_document = invoice_document.copy({
            'attachment_id': attachment.id
        })
        new_invoice = self.rule.create_record(invoice_document).get('res_id')
        self.assertNotEqual(invoice, new_invoice, 'Invoice not generated 2 times.')

    def test_invoice_refund(self):
        """Ensure that reconcile invoice and refund"""
        attachment = self.env['ir.attachment'].create({
            'name': 'vendor_bill.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        self.rule.create_record(invoice_document)
        self.invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'data', 'cfdi_refund.xml')).read().encode('UTF-8')
        attachment = self.env['ir.attachment'].create({
            'name': 'refund.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = invoice_document.copy({
            'attachment_id': attachment.id
        })
        refund = self.env['account.move'].browse(self.rule.create_record(invoice_document).get('res_id'))
        self.assertEqual(refund.move_type, 'in_refund')
        refund.button_cancel()
        self.assertEqual(refund.edi_state, 'cancelled', 'EDI state was not updated to cancelled.')

    def test_invoice_same_date(self):
        """Must be generated 2 invoices"""
        invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'invoice_240122.xml')).read().encode('UTF-8')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'invoice_2_240122.xml')).read().encode('UTF-8')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(invoice_xml),
            'description': 'Mexican invoice',
        })
        invoice_document = invoice_document.copy({
            'attachment_id': attachment.id
        })
        invoice2 = self.rule.create_record(invoice_document).get('res_id')
        self.assertNotEqual(invoice, invoice2, 'Invoice generated 1 time.')

    def test_invoice_sat_status(self):
        """Must be attached the XML on the previous invoice"""
        self.env.user.company_id.vat = 'VAU111017CG9'
        self.env.user.company_id.l10n_mx_edi_pac_test_env = False
        invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'invoice_sat.xml')).read().encode('UTF-8')
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(invoice_xml),
            'description': 'Mexican invoice',
        })
        attachment2 = attachment.copy()
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document).get('res_id')
        invoice = self.env['account.move'].browse(invoice)
        invoice2 = invoice.copy({'ref': invoice.ref})
        invoice.unlink()
        invoice_xml = misc.file_open(join(
            'l10n_mx_edi_document', 'tests', 'invoice_sat.xml')).read().encode('UTF-8')
        invoice_document = self.env['documents.document'].create({
            'name': attachment2.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment2.id
        })
        invoice3 = self.rule.create_record(invoice_document).get('res_id')
        self.assertEqual(invoice2.id, invoice3, 'Invoice generated 2 times.')
