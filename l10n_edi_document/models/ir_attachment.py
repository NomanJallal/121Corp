# Copyright 2020 Vauxoo
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def l10n_edi_document_is_xml(self):
        """Must be implemented by each Vauxoo l10n module to detect the specific fields in each business model.

        :return: If is a valid xml of an specific Vauxoo l10n will return an lxml.objectify of the xml attached
        :rtype: lxml.objectify or False
        or False."""
        return False

    def l10n_edi_document_type(self, document=False):
        """Must be implemented by each l10n module to use the specific fields for each business model.

        :return: Array with two elements:
            Array[0] is an string to identify the type of document
            Array[1] the res_model for the attachment.
        :rtype: Array"""

        return ['', '']
