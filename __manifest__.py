{
    'name': "Contabilidad Personalizada",
    'summary': "Añade campos personalizados y validaciones a las facturas",
    'description': """
        Agrega campos Serie, Numero, Tipo_DTE y Descripcion_general.
        También verifica que no se repitan Serie y Numero juntos.
    """,
    'author': "Tu Nombre",
    'website': "",
    'category': 'Accounting',
    'version': '18.0.1',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}