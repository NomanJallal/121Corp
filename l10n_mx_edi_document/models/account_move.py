# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools import float_round
from odoo.exceptions import UserError, ValidationError


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    def xml2record(self, default_account=False, analytic_account=False):
        """Use the last attachment in the invoice (xml) and fill the invoice data"""
        result = super().xml2record()
        if self.country_code != 'MX' or result._context.get('xml2record'):
            return result
        atts = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids),
        ])
        prod_supplier = self.env['product.supplierinfo']
        prod = self.env['product.product']
        sat_code = self.env['product.unspsc.code']
        uom_obj = self.env['uom.uom']
        default_account = default_account or self.journal_id.default_account_id.id
        invoice = self
        for attachment in atts:
            cfdi = attachment.l10n_mx_edi_is_cfdi33()
            if cfdi is False:
                continue
            amount = 0
            currency = self.env['res.currency'].search([('name', '=', cfdi.get('Moneda'))], limit=1)
            self.l10n_mx_edi_set_cfdi_partner(cfdi, currency)
            invoice = self._search_invoice(cfdi) or invoice
            if invoice != self:
                attachment.write({'res_id': invoice.id})
                self.unlink()
                invoice._l10n_mx_edi_update_data(attachment)
                continue
            cfdi_related = ''
            if hasattr(cfdi, 'CfdiRelacionados'):
                cfdi_related = '%s|%s' % (
                    cfdi.CfdiRelacionados.get('TipoRelacion'),
                    ','.join([rel.get('UUID') for rel in cfdi.CfdiRelacionados.CfdiRelacionado]))
            invoice_data = {
                'ref': '%s%s' % (cfdi.get('Serie', ''), cfdi.get('Folio', '')),
                'currency_id': currency.id,
                'l10n_mx_edi_post_time': cfdi.get('Fecha').replace('T', ' '),
                'l10n_mx_edi_origin': cfdi_related,
            }
            if not self.invoice_date:
                invoice_data['invoice_date'] = cfdi.get('Fecha').split('T')[0]
                invoice_data['date'] = cfdi.get('Fecha').split('T')[0]
            self.write(invoice_data)
            fiscal_position = self.fiscal_position_id
            for rec in cfdi.Conceptos.Concepto:
                name = rec.get('Descripcion', '')
                no_id = rec.get('NoIdentificacion', name)
                uom = rec.get('Unidad', '')
                uom_code = rec.get('ClaveUnidad', '')
                qty = rec.get('Cantidad', '')
                price = rec.get('ValorUnitario', '')
                amount = float(rec.get('Importe', '0.0'))
                supplierinfo = prod_supplier.search([
                    ('name', '=', self.partner_id.id),
                    '|', ('product_name', '=ilike', name),
                    ('product_code', '=ilike', no_id)], limit=1)
                product = supplierinfo.product_tmpl_id.product_variant_id
                product = product or prod.search([
                    '|', ('default_code', '=ilike', no_id),
                    ('name', '=ilike', name)], limit=1)
                accounts = product.product_tmpl_id.get_product_accounts(fiscal_pos=fiscal_position)
                account_id = (accounts['income'] if self.is_sale_document(
                    include_receipts=True) else accounts['expense']) or default_account

                discount = 0.0
                if rec.get('Descuento') and amount:
                    discount = (float(rec.get('Descuento', '0.0')) / amount) * 100

                domain_uom = [('name', '=ilike', uom)]
                code_sat = sat_code.search([('code', '=', uom_code)], limit=1)
                domain_uom = [('unspsc_code_id', '=', code_sat.id)]
                uom_id = uom_obj.with_context(lang='es_MX').search(domain_uom, limit=1)
                if rec.get('ClaveProdServ', '') in self._get_fuel_codes():
                    taxes = self.collect_taxes(rec.Impuestos.Traslados.Traslado) if hasattr(
                        rec.Impuestos, 'Traslados') else []
                    tax = taxes[0] if taxes else {}
                    qty = 1.0
                    price = tax.get('amount') / (tax.get('rate') / 100)
                    self.write({'invoice_line_ids': [(0, 0, {
                        'account_id': account_id,
                        'name':  _('FUEL - IEPS'),
                        'quantity': qty,
                        'product_uom_id': uom_id.id,
                        'price_unit': float(rec.get('Importe', 0)) - price,
                        'analytic_account_id': analytic_account,
                    })]})
                self.write({'invoice_line_ids': [(0, 0, {
                    'product_id': product.id,
                    'account_id': account_id,
                    'name': name,
                    'quantity': float(qty),
                    'analytic_account_id': analytic_account,
                    'product_uom_id': uom_id.id,
                    'tax_ids': self.get_line_taxes(rec),
                    'price_unit': float(price),
                    'discount': discount,
                })]})

            for tax in self._get_local_taxes(cfdi):
                self.write({'invoice_line_ids': [(0, 0, {
                    'account_id': default_account,
                    'name': tax[-1]['name'],
                    'quantity': 1,
                    'price_unit': tax[-1]['amount'],
                })]})

            self._l10n_mx_edi_update_data(attachment)
            if self.state == 'posted' and cfdi_related.split('|')[0] in ('01', '03'):
                move = self.line_ids.filtered(lambda line: line.account_id.internal_type in ('payable', 'receivable'))
                for uuid in self.l10n_mx_edi_origin.split('|')[1].split(','):
                    inv = self.search([('l10n_mx_edi_cfdi_uuid', '=', uuid.upper().strip())])
                    if not inv:
                        continue
                    inv.js_assign_outstanding_line(move.ids)
        return invoice

    def _l10n_mx_edi_update_data(self, attachment):
        if self.edi_state == 'sent':
            return
        self.edi_state = 'sent'
        document = self.env['account.edi.document'].create({
            'edi_format_id': self.env.ref('l10n_mx_edi.edi_cfdi_3_3').id,
            'move_id': self.id,
            'state': 'sent',
            'attachment_id': attachment.id,
        })
        sat_param = self.env['ir.config_parameter'].sudo().get_param('l10n_mx_edi_document.omit_sat_validation', False)
        if not sat_param:
            self.l10n_mx_edi_update_sat_status()
        if self.move_type in ('in_refund', 'in_invoice'):
            return
        # The invoice will be removed, then avoid validate it.
        if not sat_param and not self.company_id.l10n_mx_edi_pac_test_env and self.l10n_mx_edi_sat_status != 'valid':
            return
        try:
            self.action_post()
            # Write again because could be removed on the post method and are necessary to avoid stamp again
            document.attachment_id = attachment
            document.state = 'sent'
        except (UserError, ValidationError) as exe:
            self.message_post(body=_('<b>Error on invoice validation </b><br/>%s') % exe.name)
        return

    def l10n_mx_edi_set_cfdi_partner(self, cfdi, currency):
        self.ensure_one()
        partner = self.env['res.partner']
        domain = []
        partner_cfdi = {}
        if self.move_type in ('out_invoice', 'out_refund'):
            partner_cfdi = cfdi.Receptor
        elif self.move_type in ('in_invoice', 'in_refund'):
            partner_cfdi = cfdi.Emisor
        vat = partner_cfdi.get('Rfc')
        if vat in ('XEXX010101000', 'XAXX010101000'):
            domain.append(('name', '=', partner_cfdi.get('Nombre')))
        else:
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
        partner_param = self.env['ir.config_parameter'].sudo().get_param('mx_documents_omit_partner_generation', '')
        if not cfdi_partner and not partner_param:
            cfdi_partner = partner.create({
                'name': partner_cfdi.get('Nombre'),
                'vat': partner_cfdi.get('Rfc'),
                'country_id': self.env.ref('base.mx').id,
            })
            cfdi_partner.message_post(body=_('This record was generated from DMS'))
        if cfdi_partner:
            self.partner_id = cfdi_partner
            self._onchange_partner_id()

    def get_line_taxes(self, line):
        taxes_list = []
        if not hasattr(line, 'Impuestos'):
            return taxes_list
        taxes = []
        taxes_xml = line.Impuestos
        if hasattr(taxes_xml, 'Traslados'):
            taxes = self.collect_taxes(taxes_xml.Traslados.Traslado)
        if hasattr(taxes_xml, 'Retenciones'):
            taxes += self.collect_taxes(taxes_xml.Retenciones.Retencion)
        for tax in taxes:
            tax_group_id = self.env['account.tax.group'].search(
                [('name', 'ilike', tax['tax'])])
            domain = [
                ('tax_group_id', 'in', tax_group_id.ids),
                ('type_tax_use', '=', 'purchase' if 'in_' in self.move_type else 'sale'),
                ('company_id', '=', self.company_id.id)]
            if -10.67 <= tax['rate'] <= -10.66:
                domain.append(('amount', '<=', -10.66))
                domain.append(('amount', '>=', -10.67))
            else:
                domain.append(('amount', '=', tax['rate']))
            name = '%s(%s%%)' % (tax['tax'], tax['rate'])

            tax_get = self.env['account.tax'].search(domain, limit=1)
            if not tax_get:
                self.message_post(body=_('The tax %s cannot be found') % name)
                continue
            tax_account = tax_get.invoice_repartition_line_ids.filtered(
                lambda rec: rec.repartition_type == 'tax')
            if not tax_account:
                self.message_post(body=_(
                    'Please configure the tax account in the tax %s') % name)
                continue
            taxes_list.append((4, tax_get.id))
        return taxes_list

    def _get_local_taxes(self, xml):
        if not hasattr(xml, 'Complemento'):
            return {}
        local_taxes = xml.Complemento.xpath(
            'implocal:ImpuestosLocales', namespaces={'implocal': 'http://www.sat.gob.mx/implocal'})
        taxes = []
        if not local_taxes:
            return taxes
        local_taxes = local_taxes[0]
        if hasattr(local_taxes, 'RetencionesLocales'):
            for local_ret in local_taxes.RetencionesLocales:
                taxes.append((0, 0, {
                    'name': local_ret.get('ImpLocRetenido'),
                    'amount': float(local_ret.get('Importe')) * -1,
                }))
        if hasattr(local_taxes, 'TrasladosLocales'):
            for local_tras in local_taxes.TrasladosLocales:
                taxes.append((0, 0, {
                    'name': local_tras.get('ImpLocTrasladado'),
                    'amount': float(local_tras.get('Importe')),
                }))

        return taxes

    @staticmethod
    def collect_taxes(taxes_xml):
        """ Get tax data of the Impuesto node of the xml and return
        dictionary with taxes datas
        :param taxes_xml: Impuesto node of xml
        :type taxes_xml: etree
        :return: A list with the taxes data
        :rtype: list
        """
        taxes = []
        tax_codes = {'001': 'ISR', '002': 'IVA', '003': 'IEPS'}
        for rec in taxes_xml:
            tax_xml = rec.get('Impuesto', '')
            tax_xml = tax_codes.get(tax_xml, tax_xml)
            amount_xml = float(rec.get('Importe', '0.0'))
            rate_xml = float_round(
                float(rec.get('TasaOCuota', '0.0')) * 100, 4)
            if 'Retenciones' in rec.getparent().tag:
                amount_xml = amount_xml * -1
                rate_xml = rate_xml * -1

            taxes.append({'rate': rate_xml, 'tax': tax_xml,
                          'amount': amount_xml})
        return taxes

    def _search_invoice(self, cfdi):
        folio = cfdi.get('Folio', '')
        serie = cfdi.get('Serie', '')
        serie_folio = '%s%%%s' % (serie, folio) if serie or folio else ''
        domain = [('move_type', '=', self.move_type)]
        if self.partner_id:
            domain.extend([
                '|', ('partner_id', 'child_of', self.partner_id.id), ('partner_id', '=', self.partner_id.id)])
        # The parameter l10n_mx_force_only_folio is used when the user create the invoices from a PO and only set
        # the folio in the reference.
        force_folio = self.env['ir.config_parameter'].sudo().get_param('l10n_mx_force_only_folio', '')
        if serie_folio and force_folio:
            domain.append('|')
            domain.append(('ref', '=ilike', folio))
        if serie_folio:
            domain.append('|')
            domain.append(('name', '=ilike', serie_folio))
            domain.append(('ref', '=ilike', serie_folio))
            invoice = self.search(domain, limit=1)
            return invoice if not invoice.l10n_mx_edi_cfdi_uuid or invoice.l10n_mx_edi_cfdi_uuid == self.l10n_mx_edi_cfdi_uuid else False  # noqa
        date_type = self.env['ir.config_parameter'].sudo().get_param('documents_force_use_date')
        if date_type == "day":
            domain.append(('invoice_date', '=', fields.datetime.strptime(cfdi.get('Fecha'),
                                                                         '%Y-%m-%dT%H:%M:%S').date()))
        elif date_type == "month":
            xml_date = fields.datetime.strptime(cfdi.get('Fecha'), '%Y-%m-%dT%H:%M:%S').date()
            domain.append(('invoice_date', '>=', xml_date.replace(day=1)))
            last_day = xml_date.replace(day=1, month=xml_date.month + 1) - timedelta(days=1)
            domain.append(('invoice_date', '<=', last_day))

        amount = float(cfdi.get('Total', 0.0))
        domain.append(('amount_total', '>=', amount - 1))
        domain.append(('amount_total', '<=', amount + 1))
        domain.append(('state', '!=', 'cancel'))

        # The parameter l10n_mx_edi_vendor_bills_force_use_date is used when the user create the invoices from a PO
        # and not assign the same date that in the CFDI.
        date_type = self.env['ir.config_parameter'].sudo().get_param('l10n_mx_edi_vendor_bills_force_use_date')
        xml_date = fields.datetime.strptime(cfdi.get('Fecha'), '%Y-%m-%dT%H:%M:%S').date()

        if date_type == "day":
            domain.append(('invoice_date', '=', xml_date))
        elif date_type == "month":
            domain.append(('invoice_date', '>=', xml_date.replace(day=1)))
            last_day = xml_date.replace(day=1, month=xml_date.month + 1) - timedelta(days=1)
            domain.append(('invoice_date', '<=', last_day))

        domain.append(('l10n_mx_edi_cfdi_uuid', 'in', (False, self.l10n_mx_edi_cfdi_uuid)))
        return self.search(domain, limit=1)

    @api.model
    def _get_fuel_codes(self):
        """Return the codes that could be used in FUEL"""
        fuel_codes = [str(r) for r in range(15101500, 15101516)]
        fuel_codes.extend(self.env.user.company_id.l10n_mx_edi_fuel_code_sat_ids.mapped('code'))
        return fuel_codes

    def _get_edi_document_errors(self):
        if self.country_code != 'MX':
            return super()._get_edi_document_errors()
        errors = []
        partner_param = self.env['ir.config_parameter'].sudo().get_param('mx_documents_omit_partner_generation', '')
        if not self.partner_id and partner_param:
            errors.append(_('The partner does not exist, please create it manually and try to generate the document '
                            'again.'))
        sat_param = self.env['ir.config_parameter'].sudo().get_param('l10n_mx_edi_document.omit_sat_validation', False)
        if not sat_param and self.edi_state == 'sent' and not self.company_id.l10n_mx_edi_pac_test_env and\
                self.l10n_mx_edi_sat_status != 'valid':
            errors.append(
                _('The SAT status of this document is not valid in the SAT. (Is %s)') % self.l10n_mx_edi_sat_status)
        return errors

    def button_cancel(self):
        """Avoid set EDI state to cancel on vendor documents for MX"""
        res = super().button_cancel()

        self.filtered(lambda i: not i.l10n_mx_edi_cfdi_request).edi_document_ids.filtered(
            lambda doc: doc.attachment_id).write({'state': 'cancelled', 'error': False, 'blocking_level': False})

        return res
