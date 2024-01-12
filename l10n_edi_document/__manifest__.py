# Copyright 2020 Vauxoo
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'EDI Documents',
    'summary': '''
    Main module to allow create EDI documents on Odoo
    ''',
    'author': 'Vauxoo',
    'website': 'https://www.vauxoo.com',
    'license': 'LGPL-3',
    'category': 'Operations/Documents/Accounting',
    'version': '15.0.1.0.1',
    'depends': [
        'account',
        'documents',
    ],
    'test': [
    ],
    'data': [
        'data/data.xml',
    ],
    'demo': [
    ],
    'assets': {
        'web.assets_backend': [
            '/l10n_edi_document/static/src/sass/widget.scss',
            '/l10n_edi_document/static/src/js/checks_widget.js',
            '/l10n_edi_document/static/src/js/checklist_animation.js',
        ],
        'web.assets_qweb': [
            '/l10n_edi_document/static/src/xml/checks_widget.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
