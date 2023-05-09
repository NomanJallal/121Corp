# -*- coding: utf-8 -*-
{
    'name': "Cancelación de CFDI",

    'summary': """""",

    'description': """
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",
    'category': 'Uncategorized',
    'version': '13.0.0.1',
    'depends': ['account'],
    'data': [
        'security/edi_mx_cancel_motive.xml',
        'views/edi_mx_cancel_motive.xml',
        'views/account_move.xml',
        'views/account_payment.xml',
        'data/data.xml',
    ],
}
