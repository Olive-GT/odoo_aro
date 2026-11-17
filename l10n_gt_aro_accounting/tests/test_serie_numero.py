# tests/test_serie_numero.py
from psycopg2 import IntegrityError

from odoo import Command
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestSerieNumero(AccountTestInvoicingCommon):
    """Serie + numero es unico por empresa, contacto y tipo de documento."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.otra_empresa = cls.setup_other_company()

    def _factura(self, move_type='in_invoice', partner=None, company_data=None, serie='A1B2C3D4', numero='123456'):
        company_data = company_data or self.company_data
        company = company_data['company']
        es_compra = move_type in ('in_invoice', 'in_refund')
        cuenta = company_data['default_account_expense' if es_compra else 'default_account_revenue']
        return self.env['account.move'].with_company(company).create({
            'move_type': move_type,
            'partner_id': (partner or self.partner_a).id,
            'invoice_date': '2026-01-15',
            'serie': serie,
            'numero': numero,
            'invoice_line_ids': [Command.create({
                'name': 'Linea de prueba',
                'quantity': 1,
                'price_unit': 100.0,
                'account_id': cuenta.id,
                'tax_ids': [Command.clear()],
            })],
        })

    def test_mismo_documento_dos_veces_se_rechaza(self):
        self._factura()
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.cr.savepoint():
            self._factura()

    def test_otro_proveedor_puede_coincidir(self):
        self._factura()
        self.assertTrue(self._factura(partner=self.partner_b))

    def test_otra_empresa_puede_registrar_el_mismo_documento(self):
        """Factura entre dos empresas de la base: venta en una, compra en la otra."""
        self._factura(move_type='out_invoice')
        self.assertTrue(self._factura(move_type='in_invoice', company_data=self.otra_empresa))
        # y la misma compra tampoco choca entre empresas
        self._factura(move_type='in_invoice', serie='ZZ', numero='9')
        self.assertTrue(self._factura(move_type='in_invoice', company_data=self.otra_empresa, serie='ZZ', numero='9'))

    def test_otro_tipo_de_documento_puede_coincidir(self):
        self._factura(move_type='in_invoice')
        self.assertTrue(self._factura(move_type='in_refund'))

    def test_sin_serie_ni_numero_no_restringe(self):
        self._factura(serie=False, numero=False)
        self.assertTrue(self._factura(serie=False, numero=False))
