# tests/test_sin_inventario.py
from odoo import Command
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestSinInventario(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.con = cls.env['res.company'].create({'name': 'Con inventario'})
        cls.sin = cls.env['res.company'].create({'name': 'Sin inventario', 'sin_inventario': True})
        cls.env.user.company_ids |= cls.con | cls.sin
        cls.contacto = cls.env['res.partner'].create({'name': 'Contacto de prueba'})
        cls.bien = cls.env['product.product'].create({
            'name': 'Bien de prueba', 'type': 'consu', 'purchase_method': 'receive'})

    def _compra(self, company):
        order = self.env['purchase.order'].with_company(company).create({
            'partner_id': self.contacto.id,
            'company_id': company.id,
            'order_line': [Command.create({
                'product_id': self.bien.id, 'product_qty': 3, 'price_unit': 10.0})],
        })
        order.button_confirm()
        return order

    def _venta(self, company):
        order = self.env['sale.order'].with_company(company).create({
            'partner_id': self.contacto.id,
            'company_id': company.id,
            'order_line': [Command.create({
                'product_id': self.bien.id, 'product_uom_qty': 2, 'price_unit': 10.0})],
        })
        order.action_confirm()
        return order

    def test_compra_con_inventario_genera_recepcion(self):
        order = self._compra(self.con)
        self.assertEqual(order.state, 'purchase')
        self.assertTrue(order.picking_ids)
        self.assertEqual(order.order_line.qty_received_method, 'stock_moves')

    def test_compra_sin_inventario_no_genera_recepcion(self):
        order = self._compra(self.sin)
        self.assertEqual(order.state, 'purchase')
        self.assertFalse(order.picking_ids)
        self.assertFalse(order.order_line.move_ids)
        self.assertEqual(order.order_line.qty_received_method, 'manual')

    def test_compra_sin_inventario_se_recibe_a_mano_y_se_factura(self):
        order = self._compra(self.sin)
        order.order_line.qty_received = 3
        self.assertEqual(order.order_line.qty_received, 3)
        self.assertEqual(order.invoice_status, 'to invoice')

    def test_cambiar_cantidad_en_orden_confirmada_no_crea_recepcion(self):
        order = self._compra(self.sin)
        order.order_line.product_qty = 5
        self.assertFalse(order.picking_ids)

    def test_venta_con_inventario_genera_entrega(self):
        order = self._venta(self.con)
        self.assertTrue(order.picking_ids)
        self.assertEqual(order.order_line.qty_delivered_method, 'stock_move')

    def test_venta_sin_inventario_no_genera_entrega(self):
        order = self._venta(self.sin)
        self.assertEqual(order.state, 'sale')
        self.assertFalse(order.picking_ids)
        self.assertEqual(order.order_line.qty_delivered_method, 'manual')
