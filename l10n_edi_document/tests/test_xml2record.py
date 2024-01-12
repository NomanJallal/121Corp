# Copyright 2020 Vauxoo
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl).

import base64
from os.path import join
from unittest.mock import patch
from odoo.tools import misc

from odoo.tests.common import TransactionCase


class TestL10EdiDocumentWorkflow(TransactionCase):
    def setUp(self):
        super().setUp()
        self.rule = self.env.ref('l10n_edi_document.edi_document_rule')
        self.invoice_xml = misc.file_open(join(
            'l10n_edi_document', 'tests', 'invoice.xml')).read().encode(
                'UTF-8')
        self.finance_folder = self.env.ref('documents.documents_finance_folder')

    def test_general_create_record(self):
        # Test create_record with no attachment
        self.assertTrue(self.rule.create_record(documents=None))

        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'EDI invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        self.rule.create_record(invoice_document)
        self.assertNotEqual(self.finance_folder, invoice_document.folder_id)

    @patch('odoo.addons.l10n_edi_document.models.ir_attachment.IrAttachment.l10n_edi_document_type')
    def test_account_invoice_create_record(self, l10n_edi_document_type):
        l10n_edi_document_type.return_value = ['customerI', 'account.move']

        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'EDI invoice',
        })
        invoice_document = self.env['documents.document'].create({
            'name': attachment.name,
            'folder_id': self.finance_folder.id,
            'attachment_id': attachment.id
        })
        invoice = self.rule.create_record(invoice_document)
        self.assertEqual(self.env['account.move'].browse(invoice.get('res_id')).state, 'draft')

        l10n_edi_document_type.return_value = ['customerP', 'account.payment']

    def test_ir_attachment(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.xml',
            'datas': base64.b64encode(self.invoice_xml),
            'description': 'EDI invoice',
        })
        # Must return False because it's and abstract method
        self.assertFalse(attachment.l10n_edi_document_is_xml())

    def test_account_move(self):
        # Test xml2record as abstract method will return self
        invoice = self.env['account.move'].create({})
        self.assertIs(invoice, invoice.xml2record())

        # Test set partner method

        # Testing default domail so all records will match the domain
        self.assertTrue(invoice.l10n_edi_document_set_partner([]))
        last_partner_id = self.env['res.partner'].search([], order='id desc', limit=1).id

        # Test specific domain by id
        self.assertTrue(invoice.l10n_edi_document_set_partner([('id', '=', last_partner_id)]))

        # Test domain for no existent record
        self.assertFalse(invoice.l10n_edi_document_set_partner([('id', '=', last_partner_id + 1)]))
