# -*- coding: utf-8 -*-
{
    'name': "cfdi4 enterprise",

    'summary': """""",

    'description': """
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",
    'category': 'Uncategorized',
    'version': '13.0.1',
    'price': 149,
    'currency': 'USD',
    'depends': ['l10n_mx_edi','account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner.xml',
        'views/account_payment.xml',
        'views/account_tax.xml',
        'data/ir_cron.xml',
        'data/4.0/cfdi.xml',
        'data/4.0/payment20.xml',
        'report/invoice_pdf_report.xml',
    ],
    "images": ["images/cfdi-banner.png"],
}
