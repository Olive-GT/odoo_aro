# models/sale_order.py
from odoo import models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('company_id.sin_inventario')
    def _compute_qty_delivered_method(self):
        super()._compute_qty_delivered_method()
        for line in self:
            if line.company_id.sin_inventario and line.qty_delivered_method == 'stock_move':
                line.qty_delivered_method = 'manual'

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        con_inventario = self.filtered(lambda line: not line.company_id.sin_inventario)
        if not con_inventario:
            return True
        return super(SaleOrderLine, con_inventario)._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty)
