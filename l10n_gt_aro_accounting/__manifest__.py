{
    'name': "Contabilidad Personalizada (Guatemala - Olive Tech)",
    'summary': "Añade campos personalizados y validaciones a las facturas",
    'description': """
        Agrega campos Serie, Numero, Tipo_DTE y Descripcion_general.
        También verifica que no se repitan Serie y Numero juntos.
    """,
    'author': "Olive Tech",
    'website': "",
    'category': 'Accounting',
    'version': '18.0.1.0',
    'depends': [
        'account',
        'base',
        'report_xlsx'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_view.xml',
        'data/report_paperformat.xml',
        'views/reporte_libros_views.xml',
        'views/reporte_libros_templates.xml',
        'reports/libros_report_action.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}