# utils/report_data.py
from odoo import fields, models

class ReporteFiscalUtils(models.AbstractModel):
    _name = 'reporte.fiscal.utils'
    _description = 'Utilidades para Reportes Fiscales'

    def get_factura_data(self, date_start, date_end, journal_id, libro):
        domain = [
            ('invoice_date', '>=', date_start),
            ('invoice_date', '<=', date_end),
            ('journal_id', '=', journal_id.id),
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice', 'in_invoice'])
        ]

        facturas = self.env['account.move'].search(domain, order='invoice_date, name')

        data = []
        for move in facturas:
            partner = move.partner_id

            if libro == 'compras':
                nit = partner.vat or ''
                compania = partner.name or ''
            else:  # ventas
                nit = move.company_id.vat or ''
                compania = move.company_id.name or ''

            data.append({
                'fecha': move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else '',
                'serie': move.serie or '',
                'numero': move.numero or '',
                'nit': nit,
                'compania': compania,
                'total': move.amount_total,
            })

        return data
