from odoo import models, fields, api, _
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

    retencion_ids = fields.One2many(
        'retencion.aplicada', 'move_id', string='Retenciones', copy=False)
    amount_retenido = fields.Monetary(
        string='Total retenido', compute='_compute_amount_retenido',
        currency_field='currency_id', store=False)
    tipos_retencion_permitidos_ids = fields.Many2many(
        'retencion.tipo', string='Tipos de retención permitidos',
        compute='_compute_tipos_retencion_permitidos',
        help="Acota el selector de retenciones a los tipos aplicables al tipo de documento.")

    # Atajo que conserva la interfaz anterior: marcarlo aplica el tipo de retención
    # de ISR configurado por defecto.
    aplica_isr = fields.Boolean(string='Aplicar ISR')

    # Datos de exención de IVA del contacto, para consulta e impresión.
    partner_exento_iva = fields.Boolean(
        related='partner_id.exento_iva', string='Contacto exento de IVA', readonly=True)
    partner_exencion_resolucion = fields.Char(
        related='partner_id.exencion_resolucion', string='Resolución de exención', readonly=True)
    partner_exencion_vigente = fields.Boolean(
        related='partner_id.exencion_vigente', string='Exención vigente', readonly=True)

    @api.depends('retencion_ids.amount')
    def _compute_amount_retenido(self):
        for move in self:
            move.amount_retenido = sum(move.retencion_ids.mapped('amount'))

    @api.depends('move_type', 'company_id')
    def _compute_tipos_retencion_permitidos(self):
        for move in self:
            if move.move_type in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund'):
                move.tipos_retencion_permitidos_ids = move._tipos_retencion_disponibles()
            else:
                move.tipos_retencion_permitidos_ids = self.env['retencion.tipo']

    # ------------------------------------------------------------------
    # Cálculo de retenciones
    # ------------------------------------------------------------------

    def _lineas_base(self):
        """Líneas de la factura que forman la base de una retención.

        Excluye las líneas generadas por retenciones para que la base no dependa
        de las retenciones ya aplicadas.
        """
        self.ensure_one()
        return self.invoice_line_ids.filtered(lambda l: not l._es_linea_retencion())

    def _base_retencion(self, tipo):
        """Monto sobre el que se calcula una retención de un tipo dado."""
        self.ensure_one()
        lineas = self._lineas_base()

        if tipo.base_calculo == 'subtotal':
            return sum(lineas.mapped('price_subtotal'))
        if tipo.base_calculo == 'total':
            return sum(lineas.mapped('price_total'))

        # base_calculo == 'iva': sumamos el impuesto trasladado en la factura.
        base = 0.0
        for line in lineas:
            for tax in line.tax_ids:
                if tipo.tax_ids and tax not in tipo.tax_ids:
                    continue
                if tax.amount_type == 'percent':
                    base += line.price_subtotal * (tax.amount / 100.0)
                elif tax.amount_type == 'fixed':
                    base += tax.amount * line.quantity
        return base

    def _sync_lineas_retencion(self):
        """Regenera las líneas negativas de la factura a partir de retencion_ids."""
        for move in self:
            if move.move_type not in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund'):
                continue

            # Se eliminan primero para que la base se calcule sin ellas.
            lineas_retencion = move.invoice_line_ids.filtered(lambda l: l._es_linea_retencion())
            if lineas_retencion:
                move.invoice_line_ids -= lineas_retencion

            for retencion in move.retencion_ids:
                retencion._recalcular(move)
                if not retencion.amount:
                    continue
                account = retencion.tipo_id._get_account(move.move_type)
                move.invoice_line_ids += self.env['account.move.line'].new({
                    'name': retencion.tipo_id.code or retencion.tipo_id.name,
                    'quantity': 1,
                    'price_unit': -retencion.amount,
                    'account_id': account.id,
                    'tax_ids': [(5, 0, 0)],
                    'es_retencion': True,
                })

    def _tipos_retencion_disponibles(self):
        """Tipos de retención aplicables a esta factura."""
        self.ensure_one()
        clave = 'compras' if self.move_type in ('in_invoice', 'in_refund') else 'ventas'
        return self.env['retencion.tipo'].search([
            ('aplica_a', 'in', [clave, 'ambos']),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id),
        ])

    def _tipo_isr_por_defecto(self):
        """Tipo de retención de ISR usado por el atajo `aplica_isr`."""
        self.ensure_one()
        param = self.env['ir.config_parameter'].sudo().get_param(
            'contabilidad_custom.retencion_isr_tipo_id')
        disponibles = self._tipos_retencion_disponibles().filtered(lambda t: t.impuesto == 'isr')
        if param:
            elegido = disponibles.filtered(lambda t: t.id == int(param))
            if elegido:
                return elegido[0]
        return disponibles[0] if disponibles else self.env['retencion.tipo']

    # ------------------------------------------------------------------
    # Onchanges
    # ------------------------------------------------------------------

    @api.onchange('aplica_isr')
    def _onchange_aplica_isr(self):
        for move in self:
            isr = move.retencion_ids.filtered(lambda r: r.impuesto == 'isr')
            if not move.aplica_isr:
                move.retencion_ids -= isr
                continue
            if isr:
                continue

            tipo = move._tipo_isr_por_defecto()
            if not tipo:
                move.aplica_isr = False
                return {'warning': {
                    'title': _("Sin configuración"),
                    'message': _("No hay ningún tipo de retención de ISR configurado. "
                                 "Créalo en Contabilidad → Configuración → Tipos de Retención."),
                }}

            base = move._base_retencion(tipo)
            if base < tipo.monto_minimo:
                move.aplica_isr = False
                return {'warning': {
                    'title': _("No aplica ISR"),
                    'message': _("La base de %(base).2f es menor al mínimo de %(minimo).2f "
                                 "definido para la retención '%(tipo)s'.",
                                 base=base, minimo=tipo.monto_minimo, tipo=tipo.name),
                }}

            move.retencion_ids += self.env['retencion.aplicada'].new({'tipo_id': tipo.id})
            move._sync_lineas_retencion()

    @api.onchange('retencion_ids', 'invoice_line_ids')
    def _onchange_retenciones(self):
        for move in self:
            move._sync_lineas_retencion()
            move.aplica_isr = bool(move.retencion_ids.filtered(lambda r: r.impuesto == 'isr'))

    @api.onchange('partner_id')
    def _onchange_partner_exencion(self):
        for move in self:
            partner = move.partner_id
            if partner.exento_iva and not partner.exencion_vigente:
                return {'warning': {
                    'title': _("Exención vencida"),
                    'message': _("El contacto %s está marcado como exento de IVA pero su "
                                 "constancia de exención no está vigente.") % partner.display_name,
                }}

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------

    def _check_retenciones(self):
        for move in self:
            for retencion in move.retencion_ids:
                if not retencion.amount:
                    raise ValidationError(
                        _("La retención '%s' quedó en cero. Elimínala o corrige la factura "
                          "antes de validar.") % retencion.tipo_id.name)
                if retencion.tipo_id.requiere_constancia and not retencion.numero_constancia:
                    raise ValidationError(
                        _("Debes registrar el número de constancia de la retención '%s'.")
                        % retencion.tipo_id.name)

    def _check_exencion_vigente(self):
        for move in self:
            partner = move.partner_id
            if not partner.exento_iva:
                continue
            fecha = move.invoice_date or move.date
            if not partner._exencion_vigente_en(fecha):
                raise ValidationError(
                    _("La constancia de exención de IVA de %(nombre)s no está vigente al "
                      "%(fecha)s. Actualiza la resolución en la ficha del contacto.",
                      nombre=partner.display_name, fecha=fecha))

    def _post(self, soft=True):
        for move in self.filtered(lambda m: m.is_invoice(include_receipts=True)):
            move._check_retenciones()
            move._check_exencion_vigente()
        return super()._post(soft=soft)

    _sql_constraints = [
        ('unique_serie_numero', 'unique(serie, numero)', 'La combinación de Serie y Número debe ser única.')
    ]
