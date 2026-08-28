{
    'name': "Contabilidad Personalizada (Guatemala - Olive Tech)",
    'summary': "Campos fiscales, retenciones de ISR/IVA, exención de IVA y libros de compras y ventas",
    'description': """
        Agrega campos Serie, Numero, Tipo_DTE y Descripcion_general, y verifica
        que no se repitan Serie y Numero juntos.

        Incluye un catálogo configurable de retenciones (ISR e IVA) donde las
        tasas, tramos, bases de cálculo y cuentas contables se definen como
        datos, además del manejo de la constancia de exención de IVA por
        contacto.
    """,
    'author': "Olive Tech",
    'website': "",
    'category': 'Accounting',
    'version': '18.0.2.0',
    'depends': [
        'account',
        'base',
        'report_xlsx'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/retenciones_data.xml',
        'views/retencion_views.xml',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_view.xml',
        'views/reporte_libros_views.xml',
        'views/reporte_libros_templates.xml',
        'reports/account_move_report_compact.xml',
        'reports/libros_report_action.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
