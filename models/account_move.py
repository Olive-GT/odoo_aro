from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    serie = fields.Char(string='Serie', required=False)
    numero = fields.Char(string='Número', required=False)
    tipo_dte = fields.Selection([
        ('FACT', 'Factura'),
        ('NDEB', 'Nota de Débito'),
        ('NCRE', 'Nota de Crédito'),
        ('FPEQ', 'Factura Pequeño Contribuyente'),
        ('FESP', 'Factura Especial'),
    ], string='Tipo DTE', required=False)
    descripcion_general = fields.Text(string='Descripción General')
    aplica_isr = fields.Boolean(string='Aplicar ISR')

    @api.onchange('aplica_isr', 'invoice_line_ids')
    def _onchange_aplica_isr(self):
        for move in self:
            move.invoice_line_ids = move.invoice_line_ids.filtered(lambda l: l.name != 'ISR')
            if move.aplica_isr:

                if move.amount_untaxed <= 2500:
                    raise ValidationError("No se puede aplicar ISR si el total es menor a Q2,500.")
                isr = move._calcular_isr(move.amount_untaxed)

                account = self.env['ir.config_parameter'].sudo().get_param('contabilidad_custom.isr_account_id')
                if not account:
                    raise ValidationError("Debes configurar la cuenta contable para ISR en Ajustes → Contabilidad.")
                account = self.env['account.account'].browse(int(account))
                
                move.invoice_line_ids += self.env['account.move.line'].new({
                    'name': 'ISR',
                    'quantity': 1,
                    'price_unit': -isr,
                    'account_id': account.id,
                    'exclude_from_invoice_tab': False,
                })

    def _calcular_isr(self, total):
        if total <= 30000:
            return total * 0.05
        else:
            base_5 = 30000 * 0.05
            excedente = total - 30000
            base_7 = excedente * 0.07
            return base_5 + base_7

    _sql_constraints = [
        ('unique_serie_numero', 'unique(serie, numero)', 'La combinación de Serie y Número debe ser única.')
    ]