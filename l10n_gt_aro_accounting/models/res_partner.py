# models/res_partner.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    company_type = fields.Selection(selection_add=[('foreign', 'Extranjero')])

    @api.model
    def create(self, vals):
        vals['company_id'] = False  # Siempre contacto global
        return super().create(vals)

    def write(self, vals):
        if 'company_id' in vals:
            vals['company_id'] = False
        return super().write(vals)

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
