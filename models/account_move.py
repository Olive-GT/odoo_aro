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

    _sql_constraints = [
        ('unique_serie_numero', 'unique(serie, numero)', 'La combinación de Serie y Número debe ser única.')
    ]

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    tipo = fields.Selection([
        ('bien', 'Bien'),
        ('servicio', 'Servicio'),
        ('combustible', 'Combustible'),
    ], string='Tipo', required=False, default='bien')