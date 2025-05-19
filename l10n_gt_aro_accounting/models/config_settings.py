from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    isr_account_id = fields.Many2one(
        'account.account',
        string='Cuenta contable para ISR Proveedores',
        domain=[('deprecated', '=', False)],
        config_parameter='contabilidad_custom.isr_account_id'
    )
    isr_account_client_id = fields.Many2one(
        'account.account',
        string='Cuenta contable para ISR Clientes',
        domain=[('deprecated', '=', False)],
        config_parameter='contabilidad_custom.isr_account_client_id'
    )
