# models/retencion.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RetencionTipo(models.Model):
    """Catalogo configurable de retenciones (ISR, IVA, ...).

    Las tasas viven aqui como datos, no en codigo, para que un cambio de la SAT
    se resuelva desde la interfaz y no con un despliegue.
    """
    _name = 'retencion.tipo'
    _description = 'Tipo de Retencion'
    _order = 'impuesto, sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=False)
    code = fields.Char(string='Codigo', required=True,
                       help="Codigo corto usado como nombre de la linea generada en la factura (ej. RET-IVA-EXP).")
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)

    impuesto = fields.Selection([
        ('isr', 'ISR'),
        ('iva', 'IVA'),
    ], string='Impuesto', required=True, default='iva')

    aplica_a = fields.Selection([
        ('compras', 'Compras (proveedores)'),
        ('ventas', 'Ventas (clientes)'),
        ('ambos', 'Compras y ventas'),
    ], string='Aplica a', required=True, default='compras')

    base_calculo = fields.Selection([
        ('subtotal', 'Subtotal (base imponible)'),
        ('iva', 'Monto del IVA'),
        ('total', 'Total de la factura'),
    ], string='Base de calculo', required=True, default='subtotal',
        help="Sobre que monto se calcula la retencion. La retencion de IVA normalmente "
             "se calcula sobre el monto del IVA; la de ISR sobre el subtotal.")

    tax_ids = fields.Many2many(
        'account.tax', string='Impuestos considerados IVA',
        help="Impuestos que suman a la base cuando 'Base de calculo' es 'Monto del IVA'. "
             "Si se deja vacio se toman todos los impuestos de la factura.")

    modo_calculo = fields.Selection([
        ('porcentaje', 'Porcentaje fijo'),
        ('escalonado', 'Escalonado por tramos'),
    ], string='Modo de calculo', required=True, default='porcentaje')

    percentage = fields.Float(string='Porcentaje (%)', digits=(16, 4),
                              help="Usado cuando el modo de calculo es 'Porcentaje fijo'.")
    regla_ids = fields.One2many('retencion.regla', 'tipo_id', string='Tramos',
                                help="Usado cuando el modo de calculo es 'Escalonado por tramos'.")

    monto_minimo = fields.Float(
        string='Monto minimo de la base', digits='Product Price', default=0.0,
        help="Si la base calculada es menor a este monto no se aplica la retencion. "
             "Para el ISR de compras la SAT lo fija en Q2,500.")

    account_id = fields.Many2one(
        'account.account', string='Cuenta contable (proveedores)',
        domain=[('deprecated', '=', False)],
        help="Cuenta usada en la linea de retencion de facturas de proveedor.")
    account_client_id = fields.Many2one(
        'account.account', string='Cuenta contable (clientes)',
        domain=[('deprecated', '=', False)],
        help="Cuenta usada en la linea de retencion de facturas de cliente.")

    requiere_constancia = fields.Boolean(
        string='Requiere constancia', default=False,
        help="Exige numero de constancia antes de validar la factura. Se deja desactivado "
             "por defecto para no bloquear el flujo actual; actívalo por tipo cuando quieras "
             "que la constancia sea obligatoria.")

    company_id = fields.Many2one(
        'res.company', string='Compania',
        help="Dejar vacio para que el tipo este disponible en todas las companias.")

    _sql_constraints = [
        ('unique_code_company', 'unique(code, company_id)',
         'El codigo del tipo de retencion debe ser unico por compania.'),
    ]

    @api.constrains('modo_calculo', 'percentage', 'regla_ids')
    def _check_configuracion(self):
        for tipo in self:
            if tipo.modo_calculo == 'porcentaje' and tipo.percentage <= 0:
                raise ValidationError(
                    _("El tipo de retencion '%s' usa porcentaje fijo, por lo que el porcentaje debe ser mayor a cero.")
                    % tipo.name)
            if tipo.modo_calculo == 'escalonado' and not tipo.regla_ids:
                raise ValidationError(
                    _("El tipo de retencion '%s' usa tramos, por lo que debe definir al menos un tramo.")
                    % tipo.name)

    def _get_account(self, move_type):
        """Devuelve la cuenta contable que corresponde al tipo de documento."""
        self.ensure_one()
        es_compra = move_type in ('in_invoice', 'in_refund')
        account = self.account_id if es_compra else self.account_client_id
        if not account:
            destino = _("proveedores") if es_compra else _("clientes")
            raise ValidationError(
                _("Debes configurar la cuenta contable de %s para la retencion '%s' "
                  "en Contabilidad → Configuracion → Tipos de Retencion.") % (destino, self.name))
        return account

    def calcular(self, base):
        """Calcula el monto de la retencion sobre una base ya determinada."""
        self.ensure_one()
        if base <= 0 or base < self.monto_minimo:
            return 0.0
        if self.modo_calculo == 'porcentaje':
            return base * (self.percentage / 100.0)

        monto = 0.0
        restante = base
        limite_anterior = 0.0
        for regla in self.regla_ids.sorted(lambda r: (r.sequence, r.id)):
            # 'hasta = 0' representa el ultimo tramo, sin techo.
            limite = regla.hasta if regla.hasta > 0 else float('inf')
            tramo = min(restante, limite - limite_anterior)
            if tramo <= 0:
                continue
            monto += tramo * (regla.porcentaje / 100.0)
            restante -= tramo
            limite_anterior = limite
            if restante <= 0:
                break
        return monto


class RetencionRegla(models.Model):
    """Tramo de una retencion escalonada (ej. ISR: 5% hasta Q30,000 y 7% sobre el excedente)."""
    _name = 'retencion.regla'
    _description = 'Tramo de Retencion'
    _order = 'sequence, id'

    tipo_id = fields.Many2one('retencion.tipo', string='Tipo de retencion',
                              required=True, ondelete='cascade')
    sequence = fields.Integer(string='Secuencia', default=10)
    hasta = fields.Float(string='Base hasta', digits='Product Price',
                         help="Techo acumulado del tramo. Usar 0 en el ultimo tramo para indicar 'sin limite'.")
    porcentaje = fields.Float(string='Porcentaje (%)', digits=(16, 4), required=True)

    @api.constrains('porcentaje', 'hasta')
    def _check_valores(self):
        for regla in self:
            if regla.porcentaje <= 0:
                raise ValidationError(_("El porcentaje de un tramo debe ser mayor a cero."))
            if regla.hasta < 0:
                raise ValidationError(_("El techo de un tramo no puede ser negativo."))


class RetencionAplicada(models.Model):
    """Retencion concreta aplicada a una factura, con su constancia."""
    _name = 'retencion.aplicada'
    _description = 'Retencion Aplicada'
    _order = 'move_id, id'

    move_id = fields.Many2one('account.move', string='Factura',
                              required=True, ondelete='cascade', index=True)
    tipo_id = fields.Many2one('retencion.tipo', string='Tipo de retencion', required=True)
    impuesto = fields.Selection(related='tipo_id.impuesto', string='Impuesto', store=True)
    base = fields.Monetary(string='Base', currency_field='currency_id')
    amount = fields.Monetary(string='Retencion', currency_field='currency_id')
    numero_constancia = fields.Char(string='No. de constancia')
    fecha_constancia = fields.Date(string='Fecha de constancia')
    currency_id = fields.Many2one(related='move_id.currency_id', string='Moneda')
    company_id = fields.Many2one(related='move_id.company_id', string='Compania', store=True)

    _sql_constraints = [
        ('unique_tipo_por_move', 'unique(move_id, tipo_id)',
         'No se puede aplicar dos veces el mismo tipo de retencion a la misma factura.'),
    ]

    @api.onchange('tipo_id')
    def _onchange_tipo_id(self):
        for retencion in self:
            if retencion.tipo_id and retencion.move_id:
                retencion._recalcular()

    def _recalcular(self, move=None):
        """Recalcula base y monto a partir de la factura y el tipo.

        `move` se recibe explicitamente porque en una linea recien agregada
        dentro de un onchange el campo inverso `move_id` todavia no esta poblado.
        """
        for retencion in self:
            factura = move or retencion.move_id
            if not retencion.tipo_id or not factura:
                retencion.base = 0.0
                retencion.amount = 0.0
                continue
            retencion.base = factura._base_retencion(retencion.tipo_id)
            retencion.amount = retencion.tipo_id.calcular(retencion.base)
