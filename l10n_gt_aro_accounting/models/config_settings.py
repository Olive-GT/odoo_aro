from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Las cuentas contables de cada retención se configuran ahora en el propio
    # tipo de retención (Contabilidad → Configuración → Tipos de Retención).
    retencion_isr_tipo_id = fields.Many2one(
        'retencion.tipo',
        string='Retención de ISR por defecto',
        domain=[('impuesto', '=', 'isr')],
        config_parameter='contabilidad_custom.retencion_isr_tipo_id',
        help="Tipo de retención que se aplica al marcar 'Aplicar ISR' en una factura.")

    exencion_iva_fiscal_position_id = fields.Many2one(
        'account.fiscal.position',
        string='Posición fiscal de exención de IVA',
        config_parameter='contabilidad_custom.exencion_iva_fiscal_position_id',
        help="Posición fiscal que se asigna automáticamente a los contactos marcados "
             "como exentos de IVA. Debe mapear el IVA 12% a un impuesto exento.")

    def action_abrir_tipos_retencion(self):
        return self.env['ir.actions.act_window']._for_xml_id(
            'l10n_gt_aro_accounting.action_retencion_tipo')
