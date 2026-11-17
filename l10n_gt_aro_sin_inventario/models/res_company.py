# models/res_company.py
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    sin_inventario = fields.Boolean(
        string='No lleva inventario',
        help="Las ordenes de compra y de venta de esta empresa no generan recepciones "
             "ni entregas, aunque el producto sea de tipo Bien. Las cantidades recibidas "
             "y entregadas se anotan a mano en la orden.")
