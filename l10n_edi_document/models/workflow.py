from os.path import splitext
from odoo import _, models, fields


class WorkflowActionRuleAccount(models.Model):
    _inherit = ['documents.workflow.rule']

    create_model = fields.Selection(
        selection_add=[('l10n_edi_document.edi.document', "EDI Document")])

    def create_record(self, documents=None):
        rv = super().create_record(documents=documents)
        if not self.create_model or not documents:
            return rv
        document_ids = []
        original_ids = documents.read(['res_id'])
        for document in documents.filtered(lambda doc: not doc.res_id or doc.res_model == 'documents.document'):
            if splitext(document.name)[1].upper() != '.XML':
                continue
            attachment_id = document.attachment_id
            document_type, res_model = attachment_id.l10n_edi_document_type(document)
            if not document_type:
                self._move_document_to_incorrect_folder(document, original_ids)
                if isinstance(res_model, dict) and res_model.get('error'):
                    document.message_post(body=res_model.get('error'))
                continue
            result = self._get_document_record(document, res_model, document_type, attachment_id)
            errors = result._get_edi_document_errors()
            if errors:
                self._move_document_to_incorrect_folder(document, original_ids)
                document.message_post(body=', '.join(errors))
                # Reactive document
                document.toggle_active()
                result.unlink()
                continue
            document_ids.append(result.id)
        if not document_ids:
            return rv
        action = {
            'type': 'ir.actions.act_window',
            'res_model': result._name,
            'name': "EDI Documents",
            'view_id': False,
            'view_type': 'list',
            'view_mode': 'tree',
            'views': [(False, "list"), (False, "form")],
            'domain': [('id', 'in', document_ids)],
            'context': self._context,
        }
        if len(documents) == 1 and result:
            view_id = result.get_formview_id() if result else False
            action.update({
                'view_type': 'form',
                'view_mode': 'form',
                'views': [(view_id, "form")],
                'res_id': result.id if result else False,
                'view_id': view_id,
            })
        return action

    def _move_document_to_incorrect_folder(self, document, original_ids):
        """Move the document to incorrect folder"""
        incorrect_folder = self.env.ref('l10n_edi_document.documents_incorrect_edi_folder', False)
        rule_tc = self.env.ref('documents.documents_rule_finance_validate')
        document.tag_ids = False
        res_id = [doc['res_id'] for doc in original_ids if doc['id'] == document.id]
        document.res_id = res_id[0] if res_id else False
        document.res_model = 'documents.document'
        rule_tc.apply_actions(document.ids)
        document.folder_id = incorrect_folder

    def _get_document_record(self, document, res_model, document_type, attachment):
        """Return the document generated from the document"""
        create_values = {
            'l10n_edi_created_with_dms': True,
        }
        body = _("<p>created with DMS</p>")

        if res_model == 'account.payment':
            create_values.update(self._prepare_payment_data(document_type, document))
        elif res_model == 'account.move':
            create_values.update(self._prepare_invoice_data(document_type, document))
        result = self.env[res_model].create(create_values)
        attachment.mimetype = 'application/xml'
        result.with_context(no_new_invoice=True).message_post(body=body, attachment_ids=[attachment.id])
        document.toggle_active()
        this_attachment = attachment
        if attachment.res_model or attachment.res_id:
            this_attachment = attachment.copy()
            document.attachment_id = this_attachment.id

        this_attachment.write({
            'res_model': res_model,
            'res_id': result.id,
        })

        return result.xml2record()

    def _prepare_invoice_data(self, document_type, document):
        inv_type = {'customerI': 'out_invoice',
                    'customerE': 'out_refund',
                    'vendorI': 'in_invoice',
                    'vendorE': 'in_refund'}.get(document_type)
        return {
            'move_type': inv_type,
            'journal_id': self.env['account.move'].with_context(
                **{'default_move_type': inv_type})._get_default_journal().id,
        }

    def _prepare_payment_data(self, document_type, document):
        journal = self.env['account.journal'].search([
            ('type', 'in', ('bank', 'cash')),
            ('company_id', '=', document.company_id.id or self.env.company.id)], limit=1)
        return {
            'payment_type': 'inbound' if document_type == 'customerP' else 'outbound',
            'partner_type': 'customer' if document_type == 'customerP' else 'supplier',
            'amount': 0,
            'journal_id': journal.id,
        }
