# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import os

from lxml import etree, objectify

from odoo import tools
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestL10nMxEdiUUID(TransactionCase):
    def setUp(self):
        super().setUp()
        self.attach_model = self.env['ir.attachment']
        self.invoice_model = self.env['account.move']
        self.payment_model = self.env['account.payment']
        self.xml_expected_str = tools.file_open(os.path.join(
            'l10n_mx_edi_uuid', 'tests', 'expected_cfdi33.xml')
        ).read().encode('UTF-8')
        self.xml_expected = objectify.fromstring(self.xml_expected_str)
        self.env.user.company_id.country_id = self.env.ref('base.mx')
        self.invoice_type = 'out_invoice'

    def assign_xml_attachment(self, model,
                              uuid='100a0000-2000b-3000c-4000d-50000e060008'):
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        tfd = self.xml_expected.Complemento.xpath(attribute, namespaces=namespace)[0]
        tfd.attrib['UUID'] = uuid or ''
        if uuid is None:
            del tfd.attrib['UUID']
        xml_str = etree.tostring(self.xml_expected)
        cfdi_filename = (
            '%s-%s-MX-Invoice-3.3.xml' % (model.journal_id.code, model.payment_reference)).replace('/', '')
        attachment = self.env['ir.attachment'].create({
            'name': cfdi_filename,
            'datas': base64.encodebytes(xml_str),
            'res_id': model.id,
            'res_model': model._name,
        })
        self.env['account.edi.document'].create({
            'edi_format_id': self.env.ref('l10n_mx_edi.edi_cfdi_3_3').id,
            'move_id': model.id,
            'state': 'sent',
            'attachment_id': attachment.id,
        })
        return attachment

    def create_invoice(self):
        invoice = self.invoice_model.create({'move_type': self.invoice_type})
        invoice.name = 'invoice%s' % invoice.id
        return invoice

    def create_payment(self):
        return self.payment_model.create({
            'amount': 100,
            'partner_type': 'customer',
            'payment_type': 'inbound',
            'journal_id': self.env['account.journal'].search([('type', '=', 'bank')], limit=1).id
        })

    def test_uuid_search_invoice(self):
        inv = self.invoice_model
        invoice = self.create_invoice()
        self.assign_xml_attachment(invoice)

        invoice2 = self.create_invoice()
        self.assign_xml_attachment(invoice2, uuid=None)

        signed_edi = invoice._get_l10n_mx_edi_signed_edi_document()
        attachment = signed_edi.attachment_id
        self.assertTrue(attachment, "Attachment not found")
        attachment.refresh()
        uuid = attachment.l10n_mx_edi_cfdi_uuid
        self.assertTrue(uuid, 'The UUID must be filled')
        invoices = self.invoice_model.name_search(name=uuid)
        self.assertEqual(len(invoices), 1, "Not invoice found with the UUID %s" % uuid)

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', '=', uuid)])
        self.assertEqual(invoice.ids, invoices.ids, "Not invoice found")
        invoices = self.invoice_model.name_search(name='nonexistantuuid')
        self.assertFalse(invoices, "Shouldn't exist an invoice")

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', '=', False)])
        self.assertIn(invoice2.id, invoices.ids, "Not invoice found")
        self.assertNotIn(invoice.ids, invoices.ids, "Invoice found")

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', '!=', False)])
        self.assertEqual(invoice.ids, invoices.ids, "Not invoice found")

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', 'not in', [uuid])])
        self.assertNotIn(invoice.ids, invoices.ids, "Invoice found")

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', 'in', [uuid])])
        self.assertEqual(invoice.ids, invoices.ids, "Invoice not found")

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', 'like', uuid[:5])])
        self.assertEqual(invoice.ids, invoices.ids, "Invoice not found")

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', 'not like', uuid[:5])])
        self.assertNotIn(invoice.ids, invoices.ids, "Invoice found")

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', 'ilike', uuid[:5].upper())])
        self.assertEqual(invoice.ids, invoices.ids, "Invoice not found")

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', 'not ilike', uuid[:5].upper())])
        self.assertNotIn(invoice.id, invoices.ids, "Invoice found")

        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', 'not in', [False, uuid])])
        self.assertFalse(invoices, "Invoice found")

        all_invoices = inv.search([])
        invoices = inv.search([('l10n_mx_edi_cfdi_uuid', 'in', [False, uuid])])
        self.assertEqual(invoices, all_invoices, "Invoice not found")

        invoices = inv.search(['|', ('l10n_mx_edi_cfdi_uuid', '=', False), ('l10n_mx_edi_cfdi_uuid', '=', uuid)])
        self.assertEqual(invoices, all_invoices, "Invoice not found")

        invoices = inv.search(['&', ('l10n_mx_edi_cfdi_uuid', '=', False), ('l10n_mx_edi_cfdi_uuid', '=', uuid)])
        self.assertFalse(invoices, 'Invoice found')

        invoices = inv.search(['|', ('l10n_mx_edi_cfdi_uuid', '=', 'noexists'), ('l10n_mx_edi_cfdi_uuid', '=', uuid)])
        self.assertEqual(invoice.ids, invoices.ids, "Invoice not found")

    def test_uuid_attachment_update(self):
        invoice = self.create_invoice()
        self.assign_xml_attachment(invoice)
        signed_edi = invoice._get_l10n_mx_edi_signed_edi_document()
        attachment = signed_edi.attachment_id
        self.assertTrue(attachment, "Attachment not found")
        attachment.refresh()
        uuid = attachment.l10n_mx_edi_cfdi_uuid
        self.assertTrue(uuid, 'The UUID must be filled')
        attachment.write({'l10n_mx_edi_cfdi_uuid': 'nonexistantuuid'})
        self.assertEqual(
            attachment.l10n_mx_edi_cfdi_uuid, uuid,
            "The UUID must not change manually, only by compute")
        attachment.write({'res_model': 'account.account'})
        attachment.refresh()
        self.assertFalse(
            attachment.l10n_mx_edi_cfdi_uuid,
            'The UUID of attachment should be empty')

    def test_uuid_on_invoice_multiple_attachments(self):
        invoice = self.create_invoice()
        self.assign_xml_attachment(invoice)
        signed_edi = invoice._get_l10n_mx_edi_signed_edi_document()
        attachment = signed_edi.attachment_id
        self.assertTrue(attachment, "Attachment not found")
        attachment.refresh()
        uuid = attachment.l10n_mx_edi_cfdi_uuid
        self.assertTrue(uuid, 'The UUID must be filled')
        self.assertEqual(
            invoice.l10n_mx_edi_cfdi_uuid, uuid,
            "The invoice should have the same UUID as it's attachment")
        invoice_2 = self.create_invoice()
        self.assign_xml_attachment(invoice_2, '0002-0002-000002-000000002')
        signed_edi_2 = invoice_2._get_l10n_mx_edi_signed_edi_document()
        attachment_2 = signed_edi_2.attachment_id
        self.assertTrue(attachment_2, "Attachment not found")
        attachment_2.refresh()
        uuid_2 = attachment_2.l10n_mx_edi_cfdi_uuid
        self.assertTrue(uuid_2, 'The UUID must be filled')
        self.assertNotEqual(uuid_2, uuid)
        attachment.write({'res_id': signed_edi_2.id})
        self.assertEqual(
            invoice_2.l10n_mx_edi_cfdi_uuid, uuid_2,
            'The invoice UUID must be the same of the latest attachment')

    def test_uuid_search_payment(self):
        payment = self.create_payment()
        payment.action_post()
        self.assign_xml_attachment(payment.move_id)
        signed_edi = payment.move_id._get_l10n_mx_edi_signed_edi_document()
        attachment = signed_edi.attachment_id
        self.assertTrue(attachment, "Attachment not found")
        attachment.refresh()
        uuid = attachment.l10n_mx_edi_cfdi_uuid
        self.assertTrue(uuid, 'The UUID must be filled')
        payments = self.payment_model.name_search(name=uuid)
        self.assertEqual(len(payments), 1, "Not payment found with the UUID %s" % uuid)

        payments = self.payment_model.search([('l10n_mx_edi_cfdi_uuid', '=', uuid)])
        self.assertEqual(payment.id, payments.id, "Not payment found")

        payments = self.payment_model.name_search(name='nonexistantuuid')
        self.assertFalse(payments, "Shouldn't exist an payment")

    def test_uuid_on_payment_multiple_attachments(self):
        payment = self.create_payment()
        payment.action_post()
        self.assign_xml_attachment(payment.move_id)
        signed_edi = payment.move_id._get_l10n_mx_edi_signed_edi_document()
        attachment = signed_edi.attachment_id
        self.assertTrue(attachment, "Attachment not found")
        attachment.refresh()
        uuid = attachment.l10n_mx_edi_cfdi_uuid
        self.assertTrue(uuid, 'The UUID must be filled')
        self.assertEqual(
            payment.l10n_mx_edi_cfdi_uuid, uuid,
            "The payment should have the same UUID as it's attachment")
        payment_2 = self.create_payment()
        payment_2.action_post()
        self.assign_xml_attachment(payment_2.move_id, '0002-0002-000002-000000002')
        signed_edi_2 = payment_2.move_id._get_l10n_mx_edi_signed_edi_document()
        attachment_2 = signed_edi_2.attachment_id
        self.assertTrue(attachment_2, "Attachment not found")
        attachment_2.refresh()
        uuid_2 = attachment_2.l10n_mx_edi_cfdi_uuid
        self.assertTrue(uuid_2, 'The UUID must be filled')
        self.assertNotEqual(uuid_2, uuid)
        attachment.write({'res_id': signed_edi_2.id})
        self.assertEqual(
            payment_2.l10n_mx_edi_cfdi_uuid, uuid_2,
            'The payment UUID must be the same of the latest attachment')

    def test_uuid_invoice_duplicated(self):
        invoice = self.create_invoice()
        invoice.state = 'posted'
        self.assign_xml_attachment(invoice)
        signed_edi = invoice._get_l10n_mx_edi_signed_edi_document()
        attachment = signed_edi.attachment_id
        self.assertTrue(attachment, "Attachment not found")
        attachment.refresh()
        uuid = attachment.l10n_mx_edi_cfdi_uuid
        self.assertTrue(uuid, 'The UUID must be filled')
        self.assertEqual(
            invoice.l10n_mx_edi_cfdi_uuid, uuid,
            "The invoice should have the same UUID as it's attachment")
        invoice_2 = self.create_invoice()
        invoice_2.state = 'posted'

        # Allow duplicated for same invoice
        attachment = attachment.copy()
        with self.assertRaisesRegex(ValidationError, 'UUID duplicated'):
            attachment.write({'res_id': invoice_2.id})
        # Force a duplicated from sql to bypass odoo constraint
        self.env.cr.execute(
            "UPDATE ir_attachment SET res_id = %s WHERE id=%s", (
                invoice_2.id, attachment.id))

        payment = self.create_payment()
        payment.action_post()
        with self.assertRaisesRegex(ValidationError, 'UUID duplicated'):
            (payment.move_id | invoice)._check_uuid_duplicated()

        with self.assertRaisesRegex(ValidationError, 'UUID duplicated'):
            # Check with non-exists manually is raised
            self.invoice_model._check_uuid_duplicated()

        with self.assertRaisesRegex(ValidationError, 'UUID duplicated'):
            # Check with exists manually is raised
            invoice_2._check_uuid_duplicated()

        # Allow creates new draft invoices
        invoice_3 = self.create_invoice()
        invoice_3._check_uuid_duplicated()
        # Allow creates new posted invoices
        invoice_3.state = 'posted'
        invoice_3._check_uuid_duplicated()

        # Allow duplicated for cancel invoices
        invoice_2.state = 'cancel'
        invoice_2._check_uuid_duplicated()
        with self.assertRaisesRegex(ValidationError, 'UUID duplicated'):
            # Triggering constraint after change state to posted
            invoice_2.state = 'posted'
        invoice_2.state = 'cancel'
        invoice_2.refresh()
        self.assertEqual('cancel', invoice_2.state, 'Invoice is not cancelled.')
        # Check with non-exists manually is not raised
        self.invoice_model._check_uuid_duplicated()

        # Skip checks for non-mx companies
        invoice_2.company_id.country_id = self.env.ref('base.us')
        invoice_2.state = 'posted'

    def test_attachment_update_uuid(self):
        attachment_non_exists = self.attach_model.new({})
        attachment_non_exists.update_uuid()

        invoice = self.create_invoice()

        # Without datas
        attachment = self.assign_xml_attachment(invoice)
        attachment.refresh()
        self.assertTrue(attachment.l10n_mx_edi_cfdi_uuid)
        attachment.datas = None
        attachment.refresh()
        self.assertFalse(attachment.l10n_mx_edi_cfdi_uuid)

        # invalid xml structure
        invoice = invoice.copy()
        attachment = self.assign_xml_attachment(invoice)
        self.assertTrue(attachment.l10n_mx_edi_cfdi_uuid)
        attachment.datas = base64.b64encode(b'm')
        self.assertFalse(attachment.l10n_mx_edi_cfdi_uuid)

        # valid xml but without tfd node
        invoice = invoice.copy()
        attachment = self.assign_xml_attachment(invoice)
        self.assertTrue(attachment.l10n_mx_edi_cfdi_uuid)
        cfdi = objectify.fromstring(base64.b64decode(attachment.datas))
        cfdi.remove(cfdi.Complemento)
        attachment.datas = etree.tostring(cfdi)
        self.assertFalse(attachment.l10n_mx_edi_cfdi_uuid)

    def test_uuid_invoice_duplicated_in_invoice(self):
        self.invoice_type = 'in_invoice'
        self.test_uuid_invoice_duplicated()

    def test_attachment_update_uuid_in_invoice(self):
        self.invoice_type = 'in_invoice'
        self.test_attachment_update_uuid()

    def test_uuid_invoice_self_signed(self):
        invoice = self.create_invoice()
        invoice.state = 'posted'
        self.assign_xml_attachment(invoice)
        signed_edi = invoice._get_l10n_mx_edi_signed_edi_document()
        attachment = signed_edi.attachment_id
        self.assertTrue(attachment, "Attachment not found")
        attachment.refresh()

        self.invoice_type = 'in_invoice'
        invoice_2 = self.create_invoice()
        invoice_2.state = 'posted'
        # Allow duplicated for same invoice
        attachment = attachment.copy()
        attachment.write({'res_id': invoice_2.id})
        # Check with exists manually is  not raised
        invoice_2._check_uuid_duplicated()

        # Now should rise error because uuid duplicated on in_invoice
        invoice_3 = self.create_invoice()
        invoice_3.state = 'posted'
        # Allow duplicated for same invoice
        attachment = attachment.copy()
        with self.assertRaisesRegex(ValidationError, 'UUID duplicated'):
            attachment.write({'res_id': invoice_3.id})
        # Force a duplicated from sql to bypass odoo constraint
        self.env.cr.execute(
            "UPDATE ir_attachment SET res_id = %s WHERE id=%s", (
                invoice_3.id, attachment.id))
        with self.assertRaisesRegex(ValidationError, 'UUID duplicated'):
            # Check with exists manually is raised
            invoice_3._check_uuid_duplicated()
