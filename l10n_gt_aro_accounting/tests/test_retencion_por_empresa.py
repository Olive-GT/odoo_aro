# tests/test_retencion_por_empresa.py
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestRetencionPorEmpresa(AccountTestInvoicingCommon):
    """El catalogo de retenciones es uno; las cuentas contables son de cada empresa."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.otra_empresa = cls.setup_other_company()
        cls.tipo = cls.env.ref('l10n_gt_aro_accounting.retencion_isr_compras')

    def test_cada_empresa_tiene_su_cuenta(self):
        empresa_a = self.company_data['company']
        empresa_b = self.otra_empresa['company']
        cuenta_a = self.company_data['default_account_payable']
        cuenta_b = self.otra_empresa['default_account_payable']

        self.tipo.with_company(empresa_a).account_id = cuenta_a
        self.tipo.with_company(empresa_b).account_id = cuenta_b

        self.assertEqual(self.tipo.with_company(empresa_a)._get_account('in_invoice'), cuenta_a)
        self.assertEqual(self.tipo.with_company(empresa_b)._get_account('in_invoice'), cuenta_b)

    def test_empresa_sin_cuenta_configurada_avisa(self):
        empresa_a = self.company_data['company']
        empresa_b = self.otra_empresa['company']
        self.tipo.with_company(empresa_a).account_id = self.company_data['default_account_payable']
        self.tipo.with_company(empresa_b).account_id = False

        with self.assertRaises(ValidationError):
            self.tipo.with_company(empresa_b)._get_account('in_invoice')
