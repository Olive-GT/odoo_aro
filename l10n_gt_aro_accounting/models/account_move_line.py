# models/account_move_line.py
from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    es_retencion = fields.Boolean(
        string='Es linea de retencion', default=False, copy=False,
        help="Marca las lineas generadas automaticamente por una retencion. "
             "Estas lineas se excluyen de la base de calculo y de los libros de compras y ventas.")

    def _es_linea_retencion(self):
        """La linea corresponde a una retencion.

        Reconoce tambien el formato anterior al catalogo de retenciones, donde la
        linea de ISR se identificaba por su nombre. Asi los libros de periodos ya
        cerrados no cambian aunque la factura nunca se haya migrado.
        """
        self.ensure_one()
        return bool(self.es_retencion or (self.move_id.aplica_isr and self.name == 'ISR'))
