from odoo import models


class ReporteFiscalUtils(models.AbstractModel):
    _name = 'reporte.fiscal.utils'
    _description = 'Utilidades para Reportes Fiscales'

    def get_factura_data(self, date_start, date_end, journal_id, tax_id, libro):
        domain = [
            ('invoice_date', '>=', date_start),
            ('invoice_date', '<=', date_end),
            ('journal_id', '=', journal_id.id),
            ('state', 'in', ['posted', 'cancel']),
            ('move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund'])
        ]

        facturas = self.env['account.move'].search(domain, order='invoice_date, name')
        data = []

        global_summary = {
            'bienes':      {'base': 0, 'iva': 0, 'exento': 0, 'total': 0},
            'servicios':   {'base': 0, 'iva': 0, 'exento': 0, 'total': 0},
            'combustible': {'base': 0, 'iva': 0, 'exento': 0, 'total': 0},
            'importacion': {'base': 0, 'iva': 0, 'exento': 0, 'total': 0},
            'peq':         {'base': 0, 'iva': 0, 'exento': 0, 'total': 0},
            'count': 0,
        }

        for move in facturas:
            partner = move.partner_id

            nit = partner.vat or '' if libro == 'compras' else move.company_id.vat or ''
            compania = partner.name or '' if libro == 'compras' else move.company_id.name or ''
            multiplier = -1 if move.move_type in ['out_refund', 'in_refund'] else 1

            # Inicializamos el resumen por factura
            summary = {
                'bienes': 0,
                'bienes_exento': 0,
                'servicios': 0,
                'servicios_exento': 0,
                'combustible': 0,
                'combustible_exento': 0,
                'importacion': 0,
                'importacion_exento': 0,
                'peq': 0,
                'iva': 0,
                'total': 0,
            }

            # Si la factura está cancelada → todo en cero
            if move.state == 'cancel':
                data.append({
                    'tipo': move.tipo_dte,
                    'fecha': move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else '',
                    'serie': move.serie or '',
                    'numero': move.numero or '',
                    'nit': nit,
                    'compania': compania,
                    'total': 0.0,
                    'resumen': summary
                })
                continue

            # Si es FPEQ → todo el total va a pequeño contribuyente
            if move.tipo_dte == 'FPEQ':
                peq_total = move.amount_total * multiplier
                summary['peq'] = peq_total
                summary['total'] = peq_total
                global_summary['peq']['base'] += peq_total
                global_summary['peq']['total'] += peq_total
                global_summary['count'] += 1

                data.append({
                    'tipo': move.tipo_dte,
                    'fecha': move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else '',
                    'serie': move.serie or '',
                    'numero': move.numero or '',
                    'nit': nit,
                    'compania': compania,
                    'total': peq_total,
                    'resumen': summary
                })
                continue

            # Factura normal
            factura_total = 0

            for line in move.invoice_line_ids:
                price_subtotal = line.price_subtotal * multiplier
                price_total = line.price_total * multiplier

                has_iva = False
                other_taxes_amount = 0
                iva_amount = 0

                for tax in line.tax_ids:
                    if tax.amount_type == 'percent':
                        tax_amount = line.price_subtotal * (tax.amount / 100.0)
                    elif tax.amount_type == 'fixed':
                        tax_amount = tax.amount
                    else:
                        tax_amount = 0

                    tax_amount *= multiplier

                    if tax.id == tax_id.id:
                        iva_amount += tax_amount
                        has_iva = True
                    else:
                        other_taxes_amount += tax_amount

                # Clasificación por tipo
                product_type = line.product_id.type
                if product_type == 'service':
                    category_key = 'servicios'
                elif product_type == 'combustible':
                    category_key = 'combustible'
                elif product_type == 'importacion':
                    category_key = 'importacion'
                else:
                    category_key = 'bienes'

                if has_iva:
                    summary[category_key] += price_subtotal
                    summary['iva'] += iva_amount
                    if other_taxes_amount:
                        summary[f'{category_key}_exento'] += other_taxes_amount
                    # Acumulado global
                    global_summary[category_key]['base'] += price_subtotal
                    global_summary[category_key]['iva'] += iva_amount
                    global_summary[category_key]['exento'] += other_taxes_amount
                else:
                    summary[f'{category_key}_exento'] += price_subtotal + other_taxes_amount
                    global_summary[category_key]['exento'] += price_subtotal + other_taxes_amount

                summary['total'] += price_total
                global_summary[category_key]['total'] += price_total
                factura_total += price_total

            data.append({
                'tipo': move.tipo_dte,
                'fecha': move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else '',
                'serie': move.serie or '',
                'numero': move.numero or '',
                'nit': nit,
                'compania': compania,
                'total': factura_total,
                'resumen': summary
            })
            global_summary['count'] += 1

        return {
            'facturas': data,
            'resumen_global': global_summary
        }
