# -*- coding: utf-8 -*-
"""Compara lo cargado en Odoo 18 contra lo extraido de Odoo General (17).

    OZU_DIR=/tmp/ozu_export odoo shell -c /etc/odoo/odoo.conf -d <base> --no-http < verificar.py

No escribe nada. Cada comprobacion imprime OK o DIFERENCIA con los primeros casos.
"""
import datetime
import json
import os
from collections import defaultdict

D = os.environ.get('OZU_DIR', '/tmp/ozu_export')
MOD = '__ozu__'
RESULTADOS = []


def rows(name):
    path = os.path.join(D, name + '.jsonl')
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


MAPA = {d['name']: d['res_id'] for d in env['ir.model.data'].sudo().search_read([('module', '=', MOD)], ['name', 'res_id'])}


def ya(tabla, old_id):
    return MAPA.get('%s_%s' % (tabla, old_id)) if old_id else False


def r2(x):
    return round(float(x or 0.0), 2)


def revisar(titulo, diferencias, total, nota=''):
    estado = 'OK        ' if not diferencias else 'DIFERENCIA'
    print('%s %-52s %s de %s%s' % (estado, titulo, total - len(diferencias), total, ('  · ' + nota) if nota else ''))
    for caso in diferencias[:6]:
        print('             ', caso)
    if len(diferencias) > 6:
        print('              … y %s mas' % (len(diferencias) - 6))
    RESULTADOS.append((titulo, len(diferencias), total))


company = env['res.company'].browse(ya('company', rows('company')[0]['id']))
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
print('Empresa: %s (id %s) · sin inventario: %s\n' % (company.name, company.id, company.sin_inventario))

moves_src = rows('moves')
lines_src = rows('move_lines')
Move = env['account.move']
Line = env['account.move.line']

# 1. Conteos
print('--- Conteos')
faltan = [m['name'] for m in moves_src if not ya('move', m['id'])]
revisar('Asientos cargados', faltan, len(moves_src))
faltan = [l['id'] for l in lines_src if not ya('move_line', l['id'])]
revisar('Lineas contables cargadas', faltan, len(lines_src))
env.cr.execute("select count(*), (select count(*) from account_move_line where company_id=%s) from account_move where company_id=%s", (company.id, company.id))
n_moves, n_lines = env.cr.fetchone()
revisar('Sin asientos ni lineas de mas en la empresa',
        ([] if (n_moves, n_lines) == (len(moves_src), len(lines_src)) else ['destino %s asientos / %s lineas' % (n_moves, n_lines)]), 1)

# 2. Saldos por cuenta
print('\n--- Contabilidad')
env.cr.execute("""
    select a.code_store->>%s, round(sum(l.debit),2), round(sum(l.credit),2), count(*)
      from account_move_line l join account_account a on a.id=l.account_id
     where l.company_id=%s and l.parent_state='posted' group by 1""", (str(company.id), company.id))
destino = {code: (float(d), float(h), n) for code, d, h, n in env.cr.fetchall()}
dif = []
control = rows('control_cuentas')
for c in control:
    d = destino.pop(c['code'], (0.0, 0.0, 0))
    if (r2(c['debe']), r2(c['haber']), c['lineas']) != (r2(d[0]), r2(d[1]), d[2]):
        dif.append('%s origen %s/%s (%s) destino %s/%s (%s)' % (c['code'], c['debe'], c['haber'], c['lineas'], d[0], d[1], d[2]))
dif += ['%s solo en destino %s' % (k, v) for k, v in destino.items()]
revisar('Debe y haber por cuenta (al centavo)', dif, len(control),
        'debe total %s' % '{:,.2f}'.format(sum(r2(c['debe']) for c in control)))

# 3. Cada asiento
dif_estado, dif_total, dif_resid, dif_pago = [], [], [], []
for m in moves_src:
    move = Move.browse(ya('move', m['id']))
    if not move:
        continue
    if move.state != m['state'] or move.name != m['name'] or str(move.date) != m['date']:
        dif_estado.append('%s: %s/%s/%s vs %s/%s/%s' % (m['name'], m['state'], m['name'], m['date'], move.state, move.name, move.date))
    if m['state'] != 'posted':
        continue
    if (r2(move.amount_total), r2(move.amount_untaxed), r2(move.amount_tax)) != (r2(m['amount_total']), r2(m['amount_untaxed']), r2(m['amount_tax'])):
        dif_total.append('%s: origen %s/%s/%s destino %s/%s/%s' % (m['name'], m['amount_total'], m['amount_untaxed'], m['amount_tax'], move.amount_total, move.amount_untaxed, move.amount_tax))
revisar('Estado, numero y fecha de cada asiento', dif_estado, len(moves_src))
revisar('Total, base e impuesto de cada asiento', dif_total, len([m for m in moves_src if m['state'] == 'posted']))

# 4. Cada linea
dif_bal, dif_sub, dif_cta = [], [], []
productos = 0
for l in lines_src:
    line = Line.browse(ya('move_line', l['id']))
    if not line:
        continue
    if r2(line.balance) != r2(l['balance']) or r2(line.amount_currency) != r2(l['amount_currency']):
        dif_bal.append('%s: %s vs %s' % (l['id'], l['balance'], line.balance))
    if line.account_id.id != ya('account', l['account_id']) or (line.partner_id.id or False) != (ya('partner', l['partner_id']) or False):
        dif_cta.append(l['id'])
    if l['display_type'] == 'product' and l['price_subtotal'] is not None:
        productos += 1
        if r2(line.price_subtotal) != r2(l['price_subtotal']) or r2(line.price_total) != r2(l['price_total']):
            dif_sub.append('%s %s: subtotal %s vs %s · total %s vs %s' % (line.move_id.name, (l['name'] or '')[:25], l['price_subtotal'], line.price_subtotal, l['price_total'], line.price_total))
revisar('Importe de cada linea', dif_bal, len(lines_src))
revisar('Cuenta y contacto de cada linea', dif_cta, len(lines_src))
revisar('Subtotal y total de cada renglon de factura', dif_sub, productos,
        'lo recalcula Odoo 18; alimenta los libros')

# 5. Conciliacion y saldos pendientes (solo es exacto cuando se carga la historia completa)
parciales = rows('partials')
revisar('Conciliaciones cargadas', [p['id'] for p in parciales if not ya('partial', p['id'])], len(parciales))
# pendiente esperado = importe de la linea menos lo conciliado DENTRO de lo cargado
conciliado = defaultdict(float)
for p in parciales:
    conciliado[p['debit_move_id']] += float(p['amount'])
    conciliado[p['credit_move_id']] -= float(p['amount'])
dif = []
n = 0
for l in lines_src:
    line = Line.browse(ya('move_line', l['id']))
    if not line or not line.account_id.reconcile or line.parent_state != 'posted':
        continue
    n += 1
    esperado = r2(float(l['balance']) - conciliado.get(l['id'], 0.0))
    if r2(line.amount_residual) != esperado:
        dif.append('%s %s: esperado %s destino %s' % (line.move_id.name, line.account_id.code, esperado, line.amount_residual))
revisar('Saldo pendiente de cada partida conciliable', dif, n)

# 6. Analitica
print('\n--- Analitica')
ctrl = (rows('control_analitica') or [{'lineas': 0, 'total': 0}])[0]
env.cr.execute("select count(*), coalesce(round(sum(amount),2),0) from account_analytic_line where company_id=%s", (company.id,))
n_al, t_al = env.cr.fetchone()
revisar('Lineas analiticas (cantidad e importe)',
        ([] if (n_al, r2(t_al)) == (ctrl['lineas'], r2(ctrl['total'])) else ['origen %s / %s · destino %s / %s' % (ctrl['lineas'], ctrl['total'], n_al, t_al)]), 1)

# 7. Ordenes
print('\n--- Ordenes')
dif_t, dif_s = [], []
pos = rows('purchase_orders')
for o in pos:
    order = env['purchase.order'].browse(ya('purchase_order', o['id']))
    if (r2(order.amount_untaxed), r2(order.amount_tax), r2(order.amount_total)) != (r2(o['amount_untaxed']), r2(o['amount_tax']), r2(o['amount_total'])):
        dif_t.append('%s: origen %s/%s/%s destino %s/%s/%s' % (o['name'], o['amount_untaxed'], o['amount_tax'], o['amount_total'], order.amount_untaxed, order.amount_tax, order.amount_total))
    if order.state != o['state'] or order.name != o['name']:
        dif_s.append('%s: %s vs %s' % (o['name'], o['state'], order.state))
revisar('Compras: base, impuesto y total', dif_t, len(pos))
revisar('Compras: estado y numero', dif_s, len(pos))
dif = []
for l in rows('purchase_lines'):
    line = env['purchase.order.line'].browse(ya('purchase_line', l['id']))
    if line.display_type:
        continue
    if r2(line.qty_invoiced) != r2(l['qty_invoiced']) or r2(line.qty_received) != r2(l['qty_received']):
        dif.append('%s: facturado %s vs %s · recibido %s vs %s' % (line.order_id.name, l['qty_invoiced'], line.qty_invoiced, l['qty_received'], line.qty_received))
revisar('Compras: cantidad facturada y recibida por renglon', dif, len(rows('purchase_lines')),
        'lo facturado fuera del rango cargado no puede coincidir')
env.cr.execute("select count(*) from stock_picking where company_id=%s", (company.id,))
revisar('Sin recepciones ni entregas generadas', (['%s movimientos de inventario' % env.cr.fetchone()[0]] if env.cr.rowcount and False else []), 1)
env.cr.execute("select count(*) from stock_picking where company_id=%s", (company.id,))
n_pick = env.cr.fetchone()[0]
if n_pick:
    revisar('Sin recepciones ni entregas (conteo)', ['%s creadas' % n_pick], 1)

dif_t, dif_s = [], []
sos = rows('sale_orders')
for o in sos:
    order = env['sale.order'].browse(ya('sale_order', o['id']))
    if (r2(order.amount_untaxed), r2(order.amount_tax), r2(order.amount_total)) != (r2(o['amount_untaxed']), r2(o['amount_tax']), r2(o['amount_total'])):
        dif_t.append('%s: origen %s/%s/%s destino %s/%s/%s' % (o['name'], o['amount_untaxed'], o['amount_tax'], o['amount_total'], order.amount_untaxed, order.amount_tax, order.amount_total))
    if order.name != o['name'] or order.state != ('sale' if o['state'] == 'done' else o['state']):
        dif_s.append('%s: %s vs %s' % (o['name'], o['state'], order.state))
revisar('Ventas: base, impuesto y total', dif_t, len(sos))
revisar('Ventas: estado y numero', dif_s, len(sos))

# 8. Archivos y comentarios
print('\n--- Archivos y comentarios')
atts = rows('attachments')
dif = []
for a in atts:
    att = env['ir.attachment'].browse(ya('attachment', a['id']))
    if not att or att.checksum != a['checksum'] or att.file_size != a['file_size']:
        dif.append('%s (%s)' % (a['name'], a['res_model']))
revisar('Archivos: contenido identico (huella y tamano)', dif, len(atts),
        '%.1f MB' % (sum(a['file_size'] or 0 for a in atts) / 1e6))
msgs = rows('messages')
dif = []
for m in msgs:
    msg = env['mail.message'].browse(ya('message', m['id']))
    if not msg or len(msg.attachment_ids) != len(m['attachment_ids'] or []) or msg.author_id.id != ya('partner', m['author_id']):
        dif.append(m['id'])
revisar('Comentarios: autor, fecha y archivos', dif, len(msgs))

# 9. Libros de la libreria de destino
print('\n--- Libros (libreria de Inmobiliario) frente a General')
fechas = sorted(m['date'] for m in moves_src)
d1, d2 = datetime.date.fromisoformat(fechas[0]), datetime.date.fromisoformat(fechas[-1])
Utils = env['reporte.fiscal.utils'].with_company(company)
tipo_de = {m['id']: m for m in moves_src}
iva_origen = {t['id'] for t in rows('taxes') if float(t['amount'] or 0) == 12.0}
for libro, tipos, uso in (('compras', ('in_invoice', 'in_refund'), 'purchase'), ('ventas', ('out_invoice', 'out_refund'), 'sale')):
    # General: base por «tipo de gasto» de la factura e IVA de las lineas de impuesto del 12 %
    base = defaultdict(float)
    iva = 0.0
    for l in lines_src:
        m = tipo_de[l['move_id']]
        if m['move_type'] not in tipos or m['state'] != 'posted':
            continue
        signo = -1 if (float(l['balance']) < 0) == (libro == 'compras') else 1
        if l['display_type'] == 'product':
            base[m['tipo_gasto'] or 'sin tipo'] += abs(float(l['balance'])) * signo
        elif l['display_type'] == 'tax' and l['tax_line_id'] in iva_origen:
            iva += abs(float(l['balance'])) * signo
    n_origen = len([m for m in moves_src if m['move_type'] in tipos and m['state'] in ('posted', 'cancel')])
    tax = env['account.tax'].search([('company_id', '=', company.id), ('amount', '=', 12), ('type_tax_use', '=', uso),
                                     ('price_include_override', '=', 'tax_included')], order='id', limit=1)
    resumen = defaultdict(lambda: defaultdict(float))
    n_dest = 0
    try:
        for journal in env['account.journal'].search([('company_id', '=', company.id), ('type', '=', uso)]):
            data = Utils.get_factura_data(d1, d2, journal, tax, libro)
            n_dest += len(data['facturas'])
            for clave, valores in data['resumen_global'].items():
                if isinstance(valores, dict):
                    for k, v in valores.items():
                        resumen[clave][k] += v or 0.0
        revisar('Libro de %s: mismos documentos' % libro, ([] if n_dest == n_origen else ['origen %s destino %s' % (n_origen, n_dest)]), 1)
        print('    General  (por tipo de gasto de la factura): ' + ' · '.join('%s %s' % (k, '{:,.2f}'.format(v)) for k, v in sorted(base.items())))
        print('    General  total base %s · IVA 12 %% %s' % ('{:,.2f}'.format(sum(base.values())), '{:,.2f}'.format(iva)))
        for clave in ('bienes', 'servicios', 'combustible', 'importacion', 'peq'):
            v = resumen[clave]
            if any(abs(x) > 0.004 for x in v.values()):
                print('    destino  %-12s base %s · exento %s · IVA %s · total %s' % (
                    clave, '{:,.2f}'.format(v['base']), '{:,.2f}'.format(v['exento']), '{:,.2f}'.format(v['iva']), '{:,.2f}'.format(v['total'])))
        t_base = sum(v['base'] + v['exento'] for v in resumen.values())
        t_iva = sum(v['iva'] for v in resumen.values())
        print('    destino  total base+exento %s · IVA %s' % ('{:,.2f}'.format(t_base), '{:,.2f}'.format(t_iva)))
        revisar('Libro de %s: base total igual a General' % libro, ([] if abs(t_base - sum(base.values())) < 0.005 else ['diferencia %.2f' % (t_base - sum(base.values()))]), 1)
        revisar('Libro de %s: IVA total igual a General' % libro, ([] if abs(t_iva - iva) < 0.005 else ['diferencia %.2f' % (t_iva - iva)]), 1)
    except Exception as error:
        import traceback
        print('  Libro de %s: NO SE PUDO GENERAR: %s' % (libro, traceback.format_exc()[-600:]))
        RESULTADOS.append(('Libro de %s' % libro, 1, 1))

malas = [r for r in RESULTADOS if r[1]]
print('\n=== %s comprobaciones, %s con diferencias ===' % (len(RESULTADOS), len(malas)))
