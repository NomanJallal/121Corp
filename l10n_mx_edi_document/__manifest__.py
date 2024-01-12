# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Manage Mexican Documents',
    'version': '15.0.1.0.3',
    'author': 'Vauxoo',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': [
        'documents',
        'l10n_mx',
        'l10n_mx_edi',
        'l10n_mx_edi_uuid',
        'l10n_edi_document',
    ],
    'data': [
        'data/sat_folder.xml',
        'views/account_move_view.xml',
        'views/account_payment.xml',
        'views/documents_views.xml',
        'views/res_config_settings_views.xml',
        'views/templates.xml',
    ],
    'qweb': [
        'static/src/xml/*'
    ],
    'assets': {
        'web.assets_backend': [
            "/l10n_mx_edi_document/static/src/js/checks_widget.js",
            "/l10n_mx_edi_document/static/src/js/checklist_animation.js",
            "/l10n_mx_edi_document/static/src/js/documents_inspector.js",
            "/l10n_mx_edi_document/static/src/js/documents_dashboard.js",
        ],
        'web.assets_qweb': [
            '/l10n_mx_edi_document/static/src/xml/checks_widget.xml',
        ],
    },
    'installable': True,
}
