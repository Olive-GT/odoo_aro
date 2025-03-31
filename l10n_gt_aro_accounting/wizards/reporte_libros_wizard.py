# wizards/reporte_libros_wizard.py
from odoo import models, fields
from odoo.exceptions import ValidationError
from datetime import datetime


class ReporteLibrosWizard(models.TransientModel):
    _name = 'reporte.libros.wizard'
    _description = 'Asistente para generar reporte fiscal personalizado'

    date_start = fields.Date(string="Fecha Inicio", required=True)
    date_end = fields.Date(string="Fecha Fin", required=True)
    journal_id = fields.Many2one('account.journal', string="Diario", required=True)
    tax_id = fields.Many2one('account.tax', string="Impuesto (IVA)", required=True)
    folio_inicial = fields.Integer(string="Folio Inicial", default=1)
    libro = fields.Selection([
        ('ventas', 'Libro de Ventas'),
        ('compras', 'Libro de Compras')
    ], string="Tipo de Libro", required=True)

    def action_generar_pdf(self):
        data = self.env['reporte.fiscal.utils'].get_factura_data(
            self.date_start, self.date_end, self.journal_id, self.libro
        )
        
        # Build the complete data dictionary with all needed values
        report_data = {
            'lines': data,
            'folio_inicial': self.folio_inicial,
            'libro': self.libro,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'journal_name': self.journal_id.display_name,
            'doc_ids': self.ids,
            'doc_model': 'reporte.libros.wizard',
        }
        
        # Use direct search and report_action call instead of env.ref()
        report = self.env['ir.actions.report'].search([
            ('report_name', '=', 'l10n_gt_aro_accounting.reporte_libros_pdf_template')
        ], limit=1)
        
        if not report:
            raise UserError('No se encontró el reporte. Por favor, actualice el módulo.')
            
        return report.report_action(self, data=report_data)

    def action_generar_excel(self):
        return self.env.ref('l10n_gt_aro_accounting.reporte_libros_excel').report_action(self, data={
            'date_start': self.date_start,
            'date_end': self.date_end,
            'journal_id': self.journal_id.id,
            'tax_id': self.tax_id.id,
            'folio_inicial': self.folio_inicial,
            'libro': self.libro,
        })
