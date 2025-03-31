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
        
        # Get the report action by searching instead of using ref
        report_action = self.env['ir.actions.report'].search([
            ('report_name', '=', 'l10n_gt_aro_accounting.reporte_libros_pdf_template')
        ], limit=1)
        
        if not report_action:
            # The report doesn't exist, let's create it
            report_action = self.env['ir.actions.report'].create({
                'name': 'Reporte Libros PDF',
                'model': 'reporte.libros.wizard',
                'report_type': 'qweb-pdf',
                'report_name': 'l10n_gt_aro_accounting.reporte_libros_pdf_template',
                'report_file': 'l10n_gt_aro_accounting.reporte_libros_pdf_template',
                'print_report_name': "'Reporte_Fiscal_' + object.libro",
            })
        
        return report_action.report_action(self, data={'lines': data, 'folio_inicial': self.folio_inicial})

    def action_generar_excel(self):
        return self.env.ref('l10n_gt_aro_accounting.reporte_libros_excel').report_action(self, data={
            'date_start': self.date_start,
            'date_end': self.date_end,
            'journal_id': self.journal_id.id,
            'tax_id': self.tax_id.id,
            'folio_inicial': self.folio_inicial,
            'libro': self.libro,
        })
