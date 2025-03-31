# reports/libros_excel_report.py
from odoo import models
import io
import xlsxwriter
from odoo.http import request
from odoo.tools import date_utils


class ReporteLibrosExcel(models.AbstractModel):
    _name = 'report.l10n_gt_aro_accounting.reporte_libros_excel'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Reporte Libros Excel'

    def generate_xlsx_report(self, workbook, data, wizard):
        utils = self.env['reporte.fiscal.utils']
        lines = utils.get_factura_data(
            data['date_start'],
            data['date_end'],
            self.env['account.journal'].browse(data['journal_id']),
            data['libro']
        )

        folio = data.get('folio_inicial', 1)

        sheet = workbook.add_worksheet('Reporte')
        bold = workbook.add_format({'bold': True})
        right = workbook.add_format({'align': 'right'})
        
        headers = ['#', 'Fecha', 'Serie', 'Número', 'NIT', 'Compañía', 'Total']

        for col, h in enumerate(headers):
            sheet.write(0, col, h, bold)

        row = 1
        for i, line in enumerate(lines):
            sheet.write(row, 0, folio + i)
            sheet.write(row, 1, line['fecha'])
            sheet.write(row, 2, line['serie'])
            sheet.write(row, 3, line['numero'])
            sheet.write(row, 4, line['nit'])
            sheet.write(row, 5, line['compania'])
            sheet.write_number(row, 6, line['total'], right)
            row += 1