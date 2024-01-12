
.. figure:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
    :alt: License: LGPL-3

Validate and match CFDI Payments
================================

Added validations to check if a CFDI of payment complement received
attached to a payment is valid.

Allow generate a payment for customer/vendor staring with a CFDI in documents.
The CFDI must be in the ``Financial`` folder.

**Avoid payment creation**

This module could be used to only attach the CFDI complement in the payments
previously created by the user. Then, if the payment is not found, it could be
avoided the automatic creation of this.

To avoid the payment creation is necessary add a system parameter with the
key ``mexico_document_avoid_create_payment``, and any value.

In this case, all the CFDIs with this case will be moved to the folder
``CFDIs with document not found``.

     .. figure:: ../l10n_mx_edi_document/static/src/img/not_found.png
        :width: 600pt

Extra Features:
----------------

In some cases, the documents to import comes from a subscription, and the Serie y Folio do not
change, or are not present in the CFDI, then, when search an invoice, found the last invoice
in the system for the same partner and same totals. In this case, must be generated a new
record, so, to support this case is necessary add a system parameter with the key
``documents_force_use_date`` that could be 'month' or 'day', This will add to the domain if
the CFDI and the invoice has to have exactly the same day or in the same month.

**Avoid auto partner generation**

When an invoice is attached, search for a partner with the same VAT from the CFDI,
and in case that not found any partner with that VAT, create a new one with the
document information.

If you want to avoid the auto-creation, is necessary to generate a system parameter
with the next key ´´mx_documents_omit_partner_generation´´. And if the partner is
not found, the document will be sent to the incorrect documents folder to allow
generate manually the new partner.

.. contents::

Installation
============

To install this module, you need to:

- Not special pre-installation is required, just install as a regular Odoo
  module:

  - Download this module from `Vauxoo/mexico-document
    <https://github.com/vauxoo/mexico-document>`_
  - Add the repository folder into your odoo addons-path.
  - Go to ``Settings > Module list`` search for the current name and click in
    ``Install`` button.

Usage
=====

- Add CFDI XML file as an attachment to a payment
- Click on button Check CFDI (The payment must be on a state different to draft)

Bug Tracker
===========

Bugs are tracked on
`GitHub Issues <https://github.com/Vauxoo/mexico-document/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us smashing it by providing a detailed and
welcomed feedback
`here <https://github.com/Vauxoo/mexico-document/issues/new?body=module:%20
l10n_mx_avoid_reversal_entry%0Aversion:%20
11.0.1.0.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_

Credits
=======

**Contributors**

* Luis Torres <luis_t@vauxoo.com> (Planner/Auditor)
* José Robles <josemanuel@vauxoo.com> (Developer)

Maintainer
==========

.. figure:: https://s3.amazonaws.com/s3.vauxoo.com/description_logo.png
   :alt: Vauxoo
   :width: 600pt
