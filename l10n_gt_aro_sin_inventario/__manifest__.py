{
    'name': "Empresas sin inventario (Guatemala - Olive Tech)",
    'summary': "Permite que una empresa compre y venda productos tipo Bien sin generar recepciones ni entregas",
    'description': """
        En una base con Inventario instalado, toda orden con un producto de tipo
        Bien genera una recepcion (compras) o una entrega (ventas) que alguien
        tiene que validar. Hay empresas que no llevan inventario pero necesitan
        conservar el tipo Bien en sus productos, porque de ahi salen los libros
        de compras y ventas.

        Este modulo agrega la casilla "No lleva inventario" en la empresa. Con
        ella marcada, las ordenes de esa empresa no generan movimientos de
        inventario y las cantidades recibidas y entregadas se anotan a mano,
        igual que en una base sin Inventario. Las demas empresas no cambian.
    """,
    'author': "Olive Tech",
    'category': 'Inventory',
    'version': '18.0.1.0',
    'depends': [
        'purchase_stock',
        'sale_stock',
    ],
    'data': [
        'views/res_company_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
