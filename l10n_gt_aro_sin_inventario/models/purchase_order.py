# models/purchase_order.py
from odoo import models, api


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _create_picking(self):
        con_inventario = self.filtered(lambda order: not order.company_id.sin_inventario)
        if not con_inventario:
            return True
        return super(PurchaseOrder, con_inventario)._create_picking()


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('company_id.sin_inventario')
    def _compute_qty_received_method(self):
        super()._compute_qty_received_method()
        for line in self:
            # Sin inventario no hay movimientos de los que leer lo recibido: se anota
            # a mano, tambien para los tipos propios (combustible, importacion).
            if line.company_id.sin_inventario and line.product_id and not line.display_type:
                line.qty_received_method = 'manual'

    def _create_or_update_picking(self):
        con_inventario = self.filtered(lambda line: not line.company_id.sin_inventario)
        if not con_inventario:
            return
        return super(PurchaseOrderLine, con_inventario)._create_or_update_picking()
