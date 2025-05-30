# reports/libros_excel_report.py
from odoo import models
import io
import xlsxwriter
from odoo.http import request
from odoo.tools import date_utils
from datetime import datetime


class ReporteLibrosExcel(models.AbstractModel):
    _name = 'report.l10n_gt_aro_accounting.reporte_libros_excel'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Reporte Libros Excel'

    def generate_xlsx_report(self, workbook, data, wizard):
        # Get the data from the util method
        report_data = self.env['reporte.fiscal.utils'].get_factura_data(
            data['date_start'],
            data['date_end'],
            self.env['account.journal'].browse(data['journal_id']),
            self.env['account.tax'].browse(data['tax_id']),
            data['libro']
        )
        
        lines = report_data['facturas']
        summary = report_data['resumen_global']
        folio_inicial = data.get('folio_inicial', 1)
        
        # Get company data
        company = self.env.company
        
        # Create formats
        header_format = workbook.add_format({
            'bold': True, 
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 10,
            'bg_color': '#D3D3D3',
            'border': 1
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        subtitle_format = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        text_format = workbook.add_format({
            'font_size': 10,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        date_format = workbook.add_format({
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': 'dd/mm/yyyy'
        })
        
        number_format = workbook.add_format({
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00'
        })
        
        total_format = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'bg_color': '#F2F2F2',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'font_size': 10,
            'align': 'left',
            'valign': 'vcenter',
            'border': 1
        })
        
        cell_number_format = workbook.add_format({
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
            'border': 1
        })
        
        # FIRST SHEET - Main Data
        sheet = workbook.add_worksheet('Facturas')
        
        # Set column widths
        sheet.set_column('A:A', 5)  # #
        sheet.set_column('B:B', 8)  # Tipo
        sheet.set_column('C:C', 12)  # Fecha
        sheet.set_column('D:D', 10)  # Serie
        sheet.set_column('E:E', 15)  # Número
        sheet.set_column('F:F', 15)  # NIT
        sheet.set_column('G:G', 25)  # Compañía
        sheet.set_column('H:R', 12)  # All numeric columns
        
        # Report Title and Company Information
        current_row = 0
        libro_title = 'LIBRO DE COMPRAS Y SERVICIOS RECIBIDOS' if data['libro'] == 'compras' else 'LIBRO DE VENTAS Y SERVICIOS PRESTADOS'
        sheet.write(current_row, 0, libro_title, title_format)
        current_row += 1
        
        sheet.write(current_row, 0, company.name, subtitle_format)
        current_row += 1
        
        sheet.write(current_row, 0, f"Número de identificación tributaria: {company.vat}", text_format)
        current_row += 1
        
        sheet.write(current_row, 0, f"Nombre comercial: {company.name}", text_format)
        current_row += 1
        
        sheet.write(current_row, 0, f"Domicilio fiscal: {company.street}", text_format)
        current_row += 1
        
        date_start = datetime.strptime(data['date_start'], '%Y-%m-%d').strftime('%d/%m/%Y')
        date_end = datetime.strptime(data['date_end'], '%Y-%m-%d').strftime('%d/%m/%Y')
        sheet.write(current_row, 0, f"Registro del: {date_start} al {date_end}", text_format)
        current_row += 2  # Add extra space before table
        
        # Headers
        headers = [
            '#', 'Tipo', 'Fecha', 'Serie', 'Número', 'NIT', 'Compañía',
            'Bien.', 'Bien. Ex.', 'Serv.', 'Serv. Ex.', 'Comb.',
            'Comb. Ex.', 'Impo.', 'Impo. Exe.', 'Peq.', 'IVA', 'Total'
        ]
        
        for col, h in enumerate(headers):
            sheet.write(current_row, col, h, header_format)
        current_row += 1
        
        # Data rows
        for i, line in enumerate(lines):
            sheet.write(current_row, 0, i + 1, cell_format)
            sheet.write(current_row, 1, line['tipo'], cell_format)
            sheet.write(current_row, 2, line['fecha'], cell_format)
            sheet.write(current_row, 3, line['serie'], cell_format)
            sheet.write(current_row, 4, line['numero'], cell_format)
            sheet.write(current_row, 5, line['nit'], cell_format)
            sheet.write(current_row, 6, line['compania'], cell_format)
            
            # Write all the numeric values with proper formatting
            sheet.write(current_row, 7, line['resumen']['bienes'], cell_number_format)
            sheet.write(current_row, 8, line['resumen']['bienes_exento'], cell_number_format)
            sheet.write(current_row, 9, line['resumen']['servicios'], cell_number_format)
            sheet.write(current_row, 10, line['resumen']['servicios_exento'], cell_number_format)
            sheet.write(current_row, 11, line['resumen']['combustible'], cell_number_format)
            sheet.write(current_row, 12, line['resumen']['combustible_exento'], cell_number_format)
            sheet.write(current_row, 13, line['resumen']['importacion'], cell_number_format)
            sheet.write(current_row, 14, line['resumen']['importacion_exento'], cell_number_format)
            sheet.write(current_row, 15, line['resumen']['peq'], cell_number_format)
            sheet.write(current_row, 16, line['resumen']['iva'], cell_number_format)
            sheet.write(current_row, 17, line['resumen']['total'], cell_number_format)
            
            current_row += 1
        
        # SECOND SHEET - Summary
        summary_sheet = workbook.add_worksheet('Resumen')
        
        # Set column widths
        summary_sheet.set_column('A:A', 15)  # Category
        summary_sheet.set_column('B:E', 15)  # Numeric columns
        
        current_row = 0
        
        # Report Title and Company Information in summary sheet
        summary_sheet.write(current_row, 0, company.name, subtitle_format)
        current_row += 1
        
        summary_sheet.write(current_row, 0, f"Número de identificación tributaria: {company.vat}", text_format)
        current_row += 1
        
        summary_sheet.write(current_row, 0, f"Nombre comercial: {company.name}", text_format)
        current_row += 1
        
        summary_sheet.write(current_row, 0, f"Domicilio fiscal: {company.street}", text_format)
        current_row += 1
        
        summary_sheet.write(current_row, 0, f"Registro del: {date_start} al {date_end}", text_format)
        current_row += 2
        
        # Summary heading
        summary_sheet.write(current_row, 0, "Resumen Global", title_format)
        current_row += 1
        
        # Facturas count
        summary_sheet.write(current_row, 0, f"Cantidad de Facturas: {summary.get('count', 0)}", subtitle_format)
        current_row += 2
        
        # Summary headers
        summary_headers = ['Categoría', 'Base', 'IVA', 'Exento', 'Total']
        for col, h in enumerate(summary_headers):
            summary_sheet.write(current_row, col, h, header_format)
        current_row += 1
        
        # Summary data
        categorias = ['bienes', 'servicios', 'combustible', 'importacion', 'peq']
        total_base = total_iva = total_exento = total_total = 0
        
        for cat in categorias:
            base = summary.get(cat, {}).get('base', 0)
            iva = summary.get(cat, {}).get('iva', 0)
            exento = summary.get(cat, {}).get('exento', 0)
            total = summary.get(cat, {}).get('total', 0)
            
            summary_sheet.write(current_row, 0, cat.title(), cell_format)
            summary_sheet.write(current_row, 1, base, cell_number_format)
            summary_sheet.write(current_row, 2, iva, cell_number_format)
            summary_sheet.write(current_row, 3, exento, cell_number_format)
            summary_sheet.write(current_row, 4, total, cell_number_format)
            
            total_base += base
            total_iva += iva
            total_exento += exento
            total_total += total
            
            current_row += 1
        
        # Total row
        summary_sheet.write(current_row, 0, "Total General", total_format)
        summary_sheet.write(current_row, 1, total_base, total_format)
        summary_sheet.write(current_row, 2, total_iva, total_format)
        summary_sheet.write(current_row, 3, total_exento, total_format)
        summary_sheet.write(current_row, 4, total_total, total_format)