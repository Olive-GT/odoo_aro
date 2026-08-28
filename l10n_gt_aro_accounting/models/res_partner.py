# models/res_partner.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    company_type = fields.Selection(selection_add=[('foreign', 'Extranjero')])

    # ------------------------------------------------------------------
    # Exención de IVA
    # ------------------------------------------------------------------
    exento_iva = fields.Boolean(
        string='Exento de IVA',
        help="El contacto cuenta con constancia de exención del IVA emitida por la SAT. "
             "Al marcarlo se le asigna la posición fiscal de exención configurada en Ajustes.")
    exencion_resolucion = fields.Char(string='No. de resolución de exención')
    exencion_fecha_inicio = fields.Date(string='Vigente desde')
    exencion_fecha_vencimiento = fields.Date(string='Vigente hasta')
    exencion_vigente = fields.Boolean(
        string='Exención vigente', compute='_compute_exencion_vigente')

    # ------------------------------------------------------------------
    # Retención de IVA
    # ------------------------------------------------------------------
    agente_retenedor_iva = fields.Boolean(
        string='Agente retenedor de IVA',
        help="El contacto está calificado por la SAT como agente de retención del IVA.")
    retencion_iva_tipo_id = fields.Many2one(
        'retencion.tipo', string='Retención de IVA por defecto',
        domain=[('impuesto', '=', 'iva')],
        help="Tipo de retención de IVA que se sugiere en las facturas de este contacto.")

    @api.depends('exento_iva', 'exencion_fecha_inicio', 'exencion_fecha_vencimiento')
    def _compute_exencion_vigente(self):
        hoy = fields.Date.context_today(self)
        for partner in self:
            partner.exencion_vigente = partner._exencion_vigente_en(hoy)

    def _exencion_vigente_en(self, fecha):
        """La exención está vigente en `fecha`. Las fechas vacías no acotan la vigencia."""
        self.ensure_one()
        if not self.exento_iva:
            return False
        if not fecha:
            return True
        if self.exencion_fecha_inicio and fecha < self.exencion_fecha_inicio:
            return False
        if self.exencion_fecha_vencimiento and fecha > self.exencion_fecha_vencimiento:
            return False
        return True

    def _aplicar_posicion_fiscal_exencion(self):
        """Asigna la posición fiscal de exención configurada a los contactos exentos."""
        posicion_id = self.env['ir.config_parameter'].sudo().get_param(
            'contabilidad_custom.exencion_iva_fiscal_position_id')
        if not posicion_id:
            return
        exentos = self.filtered(lambda p: p.exento_iva and not p.property_account_position_id)
        if exentos:
            exentos.write({'property_account_position_id': int(posicion_id)})

    @api.constrains('exento_iva', 'exencion_fecha_inicio', 'exencion_fecha_vencimiento')
    def _check_exencion(self):
        for partner in self:
            inicio = partner.exencion_fecha_inicio
            fin = partner.exencion_fecha_vencimiento
            if inicio and fin and fin < inicio:
                raise ValidationError(
                    _("La fecha de vencimiento de la exención no puede ser anterior al inicio de vigencia."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['company_id'] = False  # Siempre contacto global
        partners = super().create(vals_list)
        partners._aplicar_posicion_fiscal_exencion()
        return partners

    def write(self, vals):
        if 'company_id' in vals:
            vals['company_id'] = False
        res = super().write(vals)
        if vals.get('exento_iva'):
            self._aplicar_posicion_fiscal_exencion()
        return res

    @api.constrains('vat', 'company_type')
    def _check_vat(self):
        for partner in self:
            if not partner.vat:
                continue

            vat_clean = partner.vat.replace(' ', '').upper()

            if partner.company_type == 'company':
                if vat_clean == 'CF':
                    continue
                if not re.match(r'^[0-9K]+$', vat_clean):
                    raise ValidationError("El NIT de una empresa solo puede contener números y la letra K, sin guiones ni espacios, excepto si es 'CF'.")

                # Verificación SAT
                if len(vat_clean) < 2:
                    raise ValidationError("El NIT es demasiado corto para validación.")
                verificador = vat_clean[-1]
                if verificador == 'K':
                    verificador = '10'
                secuencia = vat_clean[:-1]

                try:
                    total = 0
                    i = 2
                    for c in secuencia[::-1]:
                        total += int(c) * i
                        i += 1
                    resultante = (11 - (total % 11)) % 11
                    if str(resultante) != verificador:
                        raise ValidationError(f"El NIT {partner.vat} no es correcto (según lineamientos de la SAT).")
                except ValueError:
                    raise ValidationError("El NIT contiene caracteres inválidos para el cálculo del dígito verificador.")

                duplicates = self.env['res.partner'].search([
                    ('vat', '=', partner.vat),
                    ('id', '!=', partner.id),
                    ('company_type', '=', 'company')
                ])
                if duplicates:
                    raise ValidationError("Este NIT ya está registrado en otra empresa.")

            elif partner.company_type == 'person':
                if not re.match(r'^[0-9]+$', vat_clean):
                    raise ValidationError("El NIT de una persona solo puede contener números.")
                duplicates = self.env['res.partner'].search([
                    ('vat', '=', partner.vat),
                    ('id', '!=', partner.id),
                    ('company_type', '=', 'person')
                ])
                if duplicates:
                    raise ValidationError("Este NIT ya está registrado en otra persona.")

            elif partner.company_type == 'foreign':
                if not re.match(r'^[A-Z0-9\-]+$', vat_clean):
                    raise ValidationError("El NIT de un extranjero solo puede contener letras, números y guiones.")
