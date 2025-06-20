from odoo import models, api

class ReporteLibrosPdf(models.AbstractModel):
    _name = 'report.l10n_gt_aro_accounting.reporte_libros_pdf_template'
    _description = 'Reporte Libros PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        docids = data.get('doc_ids', docids)
        wizard = self.env['reporte.libros.wizard'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'reporte.libros.wizard',
            'docs': wizard,
            'lines': data.get('lines', []),
            'summary': data.get('summary', {}),
            'libro': data.get('libro', ''),
            'establishment_name': data.get('establishment_name', ''),
        }

