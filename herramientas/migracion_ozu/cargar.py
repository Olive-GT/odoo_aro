# -*- coding: utf-8 -*-
"""Carga en Odoo 18 lo extraido de Odoo General (17) con `extraer.sh`.

Se ejecuta dentro de `odoo shell`, nunca suelto:

    OZU_DIR=/tmp/ozu_export odoo shell -c /etc/odoo/odoo.conf -d <base> --no-http < cargar.py

Reglas de la carga:
- Cada registro creado guarda de donde vino en `ir.model.data` (modulo `__ozu__`,
  nombre `<tabla>_<id de origen>`). Por eso se puede repetir sin duplicar, cargar
  por tandas (un mes, luego otro) y deshacer.
- Los asientos se crean con sus lineas tal como estan en el origen (incluidas las
  de impuesto y las de vencimiento) y con la sincronizacion de facturas apagada:
  Odoo no recalcula nada, asi que cada importe queda al centavo.
- Las ordenes se graban directamente en su estado final; no se «confirman», asi
  que no generan recepciones, entregas ni correos.
- No confirma la transaccion si OZU_CONFIRMAR no vale 1 (ensayo en seco).
"""
import json
import logging
import os
import tarfile
import time
from collections import defaultdict

from odoo import Command
from odoo.exceptions import ValidationError, UserError

_log = logging.getLogger('migracion_ozu')
D = os.environ.get('OZU_DIR', '/tmp/ozu_export')
CONFIRMAR = os.environ.get('OZU_CONFIRMAR') == '1'
MOD = '__ozu__'
T0 = time.time()
AVISOS = defaultdict(list)


def rows(name):
    path = os.path.join(D, name + '.jsonl')
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def tr(value):
    """Texto de un campo traducible (jsonb en el origen)."""
    if isinstance(value, dict):
        return value.get('es_GT') or value.get('en_US') or next(iter(value.values()), '')
    return value or ''


def fh(valor):
    """Fecha y hora del origen (2026-09-21T17:11:04.123) al formato de Odoo."""
    return valor.replace('T', ' ')[:19] if valor else False


def paso(texto):
    print('[%6.1fs] %s' % (time.time() - T0, texto), flush=True)


# ---------------------------------------------------------------- mapa de origen
IMD = env['ir.model.data'].sudo()
MAPA = {d['name']: d['res_id'] for d in IMD.search_read([('module', '=', MOD)], ['name', 'res_id'])}
_pend = []


def ya(tabla, old_id):
    return MAPA.get('%s_%s' % (tabla, old_id)) if old_id else False


def anotar(tabla, old_id, record):
    nombre = '%s_%s' % (tabla, old_id)
    MAPA[nombre] = record.id
    _pend.append({'module': MOD, 'name': nombre, 'model': record._name, 'res_id': record.id, 'noupdate': True})


def guardar_mapa():
    if _pend:
        IMD.create(list(_pend))
        _pend.clear()


# ---------------------------------------------------------------- empresa
origen = rows('company')[0]
CID = origen['id']
gtq = env.ref('base.GTQ')
gt = env.ref('base.gt')

company = env['res.company'].browse(ya('company', CID))
if not company:
    # Si la empresa ya existe como contacto en la base de destino (otra empresa le
    # compro o le vendio), se reutiliza ese contacto: la libreria no admite NIT repetido.
    partner = env['res.partner'].with_context(active_test=False).search(
        [('vat', '=', origen['vat'])], order='is_company desc, id', limit=1)
    vals = {
        'name': origen['name'], 'currency_id': gtq.id, 'country_id': gt.id,
        'street': origen['street'], 'street2': origen['street2'], 'city': origen['city'],
        'zip': origen['zip'], 'phone': origen['phone'], 'email': origen['email'], 'vat': origen['vat'],
        'sin_inventario': True,
    }
    if partner:
        vals['partner_id'] = partner.id
    # `chart_template_load`: al crear una empresa con pais, Odoo deja programada la
    # carga del plan de cuentas generico de Guatemala, que reemplazaria el plan
    # propio de la empresa que se carga mas abajo. Con este contexto no se programa.
    company = env['res.company'].with_context(chart_template_load=True).create(vals)
    anotar('company', CID, company)
    paso('Empresa creada: %s (id %s)' % (company.name, company.id))
env.user.company_ids |= company
env = env(context=dict(
    env.context, allowed_company_ids=[company.id], tracking_disable=True, mail_create_nolog=True,
    mail_create_nosubscribe=True, mail_notrack=True))
company = company.with_env(env)

# Odoo exige un almacen por empresa para poder crear ordenes, aunque la empresa no
# lleve inventario (la casilla «No lleva inventario» evita que se use).
Warehouse = env['stock.warehouse'].sudo()
if not Warehouse.with_context(active_test=False).search([('company_id', '=', company.id)], limit=1):
    Warehouse.create({'name': company.name, 'code': 'OZU', 'company_id': company.id,
                      'partner_id': company.partner_id.id})

# ---------------------------------------------------------------- catalogos simples
cur_origen = {c['id']: c['name'] for c in rows('currencies')}
_cur = {}


def moneda(old_id):
    if not old_id:
        return False
    nombre = cur_origen[old_id]
    if nombre not in _cur:
        _cur[nombre] = env['res.currency'].with_context(active_test=False).search([('name', '=', nombre)], limit=1).id
    return _cur[nombre]


uom_origen = {u['id']: tr(u['name']) for u in rows('uoms')}
_uom = {}
uom_unidad = env.ref('uom.product_uom_unit')


def uom(old_id):
    if not old_id:
        return uom_unidad.id
    nombre = uom_origen.get(old_id)
    if nombre not in _uom:
        found = env['uom.uom'].with_context(lang='en_US').search([('name', '=', nombre)], limit=1) \
            or env['uom.uom'].search([('name', '=', nombre)], limit=1)
        if not found:
            AVISOS['unidad de medida no encontrada, se uso Unidades'].append(nombre)
        _uom[nombre] = (found or uom_unidad).id
    return _uom[nombre]


Rate = env['res.currency.rate']
for r in rows('currency_rates'):
    cid = moneda(r['currency_id'])
    if cid and not Rate.search([('currency_id', '=', cid), ('company_id', '=', company.id), ('name', '=', r['name'])], limit=1):
        Rate.create({'currency_id': cid, 'company_id': company.id, 'name': r['name'], 'rate': r['rate']})

# ---------------------------------------------------------------- cuentas
Account = env['account.account'].with_company(company)
nuevas = 0
for a in rows('accounts'):
    if ya('account', a['id']):
        continue
    rec = Account.create({
        'code': a['code'], 'name': tr(a['name']), 'account_type': a['account_type'],
        'reconcile': a['reconcile'], 'currency_id': moneda(a['currency_id']),
        'company_ids': [Command.set([company.id])],
    })
    if a['deprecated']:
        AVISOS['cuenta obsoleta en el origen (se carga activa para poder registrar su historia)'].append(a['code'])
    anotar('account', a['id'], rec)
    nuevas += 1
guardar_mapa()
paso('Cuentas: %s nuevas' % nuevas)


def cuenta(old_id):
    return ya('account', old_id)


# ---------------------------------------------------------------- impuestos
TaxGroup = env['account.tax.group']
for g in rows('tax_groups'):
    if not ya('tax_group', g['id']):
        anotar('tax_group', g['id'], TaxGroup.create({
            'name': tr(g['name']), 'sequence': g['sequence'] or 10, 'company_id': company.id, 'country_id': gt.id}))

rep_por_tax = defaultdict(list)
for r in rows('tax_rep_lines'):
    rep_por_tax[r['tax_id']].append(r)

Tax = env['account.tax'].with_company(company)
nuevas = 0
for t in rows('taxes'):
    if ya('tax', t['id']):
        continue

    def reparto(doc):
        lineas = [r for r in rep_por_tax[t['id']] if r['document_type'] == doc]
        return [Command.create({
            'repartition_type': r['repartition_type'], 'factor_percent': r['factor_percent'],
            'account_id': cuenta(r['account_id']), 'document_type': doc,
            'use_in_tax_closing': bool(r['use_in_tax_closing']),
        }) for r in lineas], lineas

    inv_cmds, inv_src = reparto('invoice')
    ref_cmds, ref_src = reparto('refund')
    # Los impuestos «por codigo» (formula Python) del origen pasan a porcentaje: los
    # importes historicos se cargan tal cual, y en adelante las retenciones se
    # manejan con el catalogo de la libreria, no con formulas.
    tipo = t['amount_type'] if t['amount_type'] in ('percent', 'fixed', 'division', 'group') else 'percent'
    if t['amount_type'] == 'code':
        AVISOS['impuesto con formula en el origen, cargado como porcentaje'].append(tr(t['name']))
    rec = Tax.create({
        'name': tr(t['name']), 'description': tr(t['description']) or False,
        'invoice_label': tr(t['invoice_label']) or False,
        'amount_type': tipo, 'amount': t['amount'], 'type_tax_use': t['type_tax_use'],
        'price_include_override': 'tax_included' if t['price_include'] else 'tax_excluded',
        'include_base_amount': t['include_base_amount'], 'tax_exigibility': t['tax_exigibility'] or 'on_invoice',
        'tax_group_id': ya('tax_group', t['tax_group_id']), 'active': t['active'], 'sequence': t['sequence'],
        'company_id': company.id, 'country_id': gt.id,
        'invoice_repartition_line_ids': inv_cmds, 'refund_repartition_line_ids': ref_cmds,
    })
    anotar('tax', t['id'], rec)
    for src, new in zip(inv_src, rec.invoice_repartition_line_ids.sorted('id')):
        anotar('tax_rep', src['id'], new)
    for src, new in zip(ref_src, rec.refund_repartition_line_ids.sorted('id')):
        anotar('tax_rep', src['id'], new)
    nuevas += 1
guardar_mapa()
paso('Impuestos: %s nuevos' % nuevas)

# ---------------------------------------------------------------- diarios
Journal = env['account.journal'].with_company(company)
nuevas = 0
for j in rows('journals'):
    if ya('journal', j['id']):
        continue
    vals = {
        'name': tr(j['name']), 'code': j['code'], 'type': j['type'], 'company_id': company.id,
        'active': j['active'], 'sequence': j['sequence'],
    }
    if cuenta(j['default_account_id']):
        vals['default_account_id'] = cuenta(j['default_account_id'])
    jc = moneda(j['currency_id'])
    if jc and jc != gtq.id:
        vals['currency_id'] = jc
    anotar('journal', j['id'], Journal.create(vals))
    nuevas += 1
guardar_mapa()
paso('Diarios: %s nuevos' % nuevas)

# ---------------------------------------------------------------- analitica
plan = env['account.analytic.plan'].search([], order='id', limit=1)
Analytic = env['account.analytic.account']
nuevas = 0
for a in rows('analytic_accounts'):
    if ya('analytic', a['id']):
        continue
    anotar('analytic', a['id'], Analytic.create({
        'name': tr(a['name']), 'code': a['code'] or False, 'plan_id': plan.id,
        'company_id': company.id, 'active': a['active']}))
    nuevas += 1
guardar_mapa()
paso('Cuentas analiticas: %s nuevas (plan «%s»)' % (nuevas, plan.name))


def distribucion(dist):
    """Reescribe las llaves de una distribucion analitica con los ids nuevos."""
    if not dist:
        return False
    nueva = {}
    for llave, pct in dist.items():
        ids = [str(ya('analytic', int(x))) for x in str(llave).split(',') if ya('analytic', int(x))]
        if not ids:
            AVISOS['cuenta analitica de la distribucion no encontrada'].append(llave)
            continue
        nueva[','.join(ids)] = pct
    return nueva or False


# ---------------------------------------------------------------- contactos
Partner = env['res.partner']


def limpio(vat):
    return (vat or '').replace(' ', '').replace('-', '').replace('.', '').upper() or False


nuevas = reusados = 0
for p in rows('partners'):
    if ya('partner', p['id']):
        continue
    vat = limpio(p['vat'])
    tipo = 'company' if p['is_company'] else 'person'
    rec = False
    if vat and vat != 'CF':
        rec = Partner.with_context(active_test=False).search([('vat', '=', vat), ('company_type', '=', tipo)], limit=1) \
            or Partner.with_context(active_test=False).search([('vat', '=', vat)], limit=1)
    if rec:
        reusados += 1
    else:
        vals = {
            'name': p['name'] or 'SIN NOMBRE (%s)' % p['id'], 'company_type': tipo, 'is_company': p['is_company'],
            'type': p['type'] or 'contact', 'street': p['street'], 'street2': p['street2'], 'city': p['city'],
            'zip': p['zip'], 'phone': p['phone'], 'mobile': p['mobile'], 'email': p['email'], 'website': p['website'],
            'ref': p['ref'], 'comment': p['comment'], 'active': p['active'],
            'supplier_rank': p['supplier_rank'] or 0, 'customer_rank': p['customer_rank'] or 0,
            'parent_id': ya('partner', p['parent_id']) or False, 'vat': vat,
        }
        try:
            with env.cr.savepoint():
                rec = Partner.create(vals)
        except (ValidationError, UserError) as error:
            # La libreria de destino valida el NIT (digito verificador, repetidos). El
            # contacto se carga igual, sin NIT, y el NIT original queda en la nota.
            vals['vat'] = False
            vals['comment'] = ((p['comment'] or '') + '<p>NIT en Odoo General: %s (no paso la validacion)</p>' % p['vat'])
            rec = Partner.create(vals)
            AVISOS['contacto cargado SIN NIT: no paso la validacion'].append('%s | %s | %s' % (p['name'], p['vat'], str(error).split('\n')[0][:70]))
        nuevas += 1
    anotar('partner', p['id'], rec)
guardar_mapa()
paso('Contactos: %s nuevos, %s ya existian en la base (mismo NIT)' % (nuevas, reusados))


def contacto(old_id):
    return ya('partner', old_id) or False


usuarios = {u['id']: u for u in rows('users')}
_usr = {}


def usuario(old_id):
    """Usuario de destino con el mismo correo de acceso, si existe."""
    if not old_id or old_id not in usuarios:
        return False
    login = usuarios[old_id]['login']
    if login not in _usr:
        _usr[login] = env['res.users'].with_context(active_test=False).search([('login', '=', login)], limit=1).id
    return _usr[login]


# ---------------------------------------------------------------- productos
Product = env['product.product']
nuevas = 0
for p in rows('products'):
    if ya('product', p['id']):
        continue
    tipo = 'service' if p['detailed_type'] == 'service' else 'consu'
    rec = Product.create({
        'name': tr(p['name']), 'default_code': p['default_code'] or False, 'type': tipo,
        'is_storable': False, 'purchase_method': p['purchase_method'] or 'receive',
        'invoice_policy': p['invoice_policy'] or 'order', 'uom_id': uom(p['uom_id']), 'uom_po_id': uom(p['uom_po_id']),
        'list_price': p['list_price'] or 0.0, 'sale_ok': p['sale_ok'], 'purchase_ok': p['purchase_ok'],
        'description_purchase': tr(p['description_purchase']) or False,
        'description_sale': tr(p['description_sale']) or False,
        'company_id': company.id, 'active': p['active'], 'taxes_id': False, 'supplier_taxes_id': False,
    })
    anotar('product', p['id'], rec)
    nuevas += 1
guardar_mapa()
paso('Productos: %s nuevos' % nuevas)

# ---------------------------------------------------------------- cuentas por defecto
Default = env['ir.default']
puestos = 0
for pr in rows('properties'):
    ref = pr['value_reference'] or ''
    if not ref.startswith('account.account,'):
        continue
    nueva = cuenta(int(ref.split(',')[1]))
    if not nueva:
        continue
    if not pr['res_id']:
        if pr['model'] in env and pr['name'] in env[pr['model']]._fields:
            Default.set(pr['model'], pr['name'], nueva, company_id=company.id)
            puestos += 1
    elif pr['model'] == 'res.partner':
        pid = contacto(int(pr['res_id'].split(',')[1]))
        if pid:
            Partner.browse(pid).with_company(company)[pr['name']] = nueva
            puestos += 1
paso('Cuentas por defecto (contactos, categorias): %s' % puestos)

# ---------------------------------------------------------------- ordenes de compra
PO = env['purchase.order'].with_company(company)
lineas_po = defaultdict(list)
for line in rows('purchase_lines'):
    lineas_po[line['order_id']].append(line)
nuevas = 0
for o in rows('purchase_orders'):
    if ya('purchase_order', o['id']):
        continue
    cmds = []
    for line in lineas_po[o['id']]:
        if line['display_type']:
            cmds.append(Command.create({'display_type': line['display_type'], 'name': line['name'],
                                        'sequence': line['sequence'], 'product_qty': 0}))
            continue
        cmds.append(Command.create({
            'product_id': ya('product', line['product_id']), 'name': line['name'], 'sequence': line['sequence'],
            'product_qty': line['product_qty'], 'product_uom': uom(line['product_uom']),
            'price_unit': line['price_unit'], 'discount': line['discount'] or 0.0,
            'date_planned': fh(line['date_planned'] or o['date_order']),
            'taxes_id': [Command.set([ya('tax', t) for t in (line['tax_ids'] or []) if ya('tax', t)])],
            'analytic_distribution': distribucion(line['analytic_distribution']),
            'qty_received_manual': line['qty_received'] or 0.0,
        }))
    rec = PO.create({
        'name': o['name'], 'partner_id': contacto(o['partner_id']), 'partner_ref': o['partner_ref'],
        'date_order': fh(o['date_order']), 'date_approve': fh(o['date_approve']), 'date_planned': fh(o['date_planned']),
        'currency_id': moneda(o['currency_id']), 'company_id': company.id, 'state': o['state'],
        'notes': o['notes'], 'origin': o['origin'], 'user_id': usuario(o['user_id']), 'order_line': cmds,
    })
    anotar('purchase_order', o['id'], rec)
    for src, new in zip(lineas_po[o['id']], rec.order_line.sorted('id')):
        anotar('purchase_line', src['id'], new)
    nuevas += 1
guardar_mapa()
paso('Ordenes de compra: %s nuevas' % nuevas)

# ---------------------------------------------------------------- ordenes de venta
SO = env['sale.order'].with_company(company)
lineas_so = defaultdict(list)
for line in rows('sale_lines'):
    lineas_so[line['order_id']].append(line)
nuevas = 0
for o in rows('sale_orders'):
    if ya('sale_order', o['id']):
        continue
    cmds = []
    for line in lineas_so[o['id']]:
        if line['display_type']:
            cmds.append(Command.create({'display_type': line['display_type'], 'name': line['name'],
                                        'sequence': line['sequence']}))
            continue
        cmds.append(Command.create({
            'product_id': ya('product', line['product_id']), 'name': line['name'], 'sequence': line['sequence'],
            'product_uom_qty': line['product_uom_qty'], 'product_uom': uom(line['product_uom']),
            'price_unit': line['price_unit'], 'discount': line['discount'] or 0.0,
            'tax_id': [Command.set([ya('tax', t) for t in (line['tax_ids'] or []) if ya('tax', t)])],
            'analytic_distribution': distribucion(line['analytic_distribution']),
            'qty_delivered': line['qty_delivered'] or 0.0,
        }))
    rec = SO.create({
        'name': o['name'], 'partner_id': contacto(o['partner_id']),
        'partner_invoice_id': contacto(o['partner_invoice_id']) or contacto(o['partner_id']),
        'partner_shipping_id': contacto(o['partner_shipping_id']) or contacto(o['partner_id']),
        'client_order_ref': o['client_order_ref'], 'date_order': fh(o['date_order']), 'validity_date': o['validity_date'],
        'currency_id': moneda(o['currency_id']), 'company_id': company.id,
        'state': 'sale' if o['state'] == 'done' else o['state'], 'locked': bool(o['locked']) or o['state'] == 'done',
        'note': o['note'], 'origin': o['origin'], 'user_id': usuario(o['user_id']), 'order_line': cmds,
    })
    anotar('sale_order', o['id'], rec)
    for src, new in zip(lineas_so[o['id']], rec.order_line.sorted('id')):
        anotar('sale_line', src['id'], new)
    nuevas += 1
guardar_mapa()
paso('Ordenes de venta: %s nuevas' % nuevas)

# ---------------------------------------------------------------- asientos
Move = env['account.move'].with_company(company).with_context(
    skip_invoice_sync=True, check_move_validity=False, skip_readonly_check=True)
lineas_mv = defaultdict(list)
for line in rows('move_lines'):
    lineas_mv[line['move_id']].append(line)
FACTURAS = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')
TIPO_DTE = {'out_invoice': 'FACT', 'in_invoice': 'FACT', 'out_refund': 'NCRE', 'in_refund': 'NCRE'}


def vals_linea(line):
    vals = {
        'name': line['name'], 'sequence': line['sequence'], 'display_type': line['display_type'] or 'product',
        'account_id': cuenta(line['account_id']), 'partner_id': contacto(line['partner_id']),
    }
    if line['display_type'] in ('line_section', 'line_note'):
        return {'name': line['name'], 'sequence': line['sequence'], 'display_type': line['display_type']}
    vals.update({
        'currency_id': moneda(line['currency_id']) or gtq.id,
        'balance': line['balance'], 'amount_currency': line['amount_currency'],
        'quantity': line['quantity'], 'price_unit': line['price_unit'] or 0.0, 'discount': line['discount'] or 0.0,
        'product_id': ya('product', line['product_id']) or False,
        'product_uom_id': uom(line['product_uom_id']) if line['product_uom_id'] else False,
        'tax_ids': [Command.set([ya('tax', t) for t in (line['tax_ids'] or []) if ya('tax', t)])],
        'tax_line_id': ya('tax', line['tax_line_id']) or False,
        'tax_repartition_line_id': ya('tax_rep', line['tax_repartition_line_id']) or False,
        'tax_base_amount': line['tax_base_amount'] or 0.0,
        'date_maturity': line['date_maturity'],
        'analytic_distribution': distribucion(line['analytic_distribution']),
        'purchase_line_id': ya('purchase_line', line['purchase_line_id']) or False,
    })
    ventas = [ya('sale_line', s) for s in (line['sale_line_ids'] or []) if ya('sale_line', s)]
    if ventas:
        vals['sale_line_ids'] = [Command.set(ventas)]
    return vals


pendientes = [m for m in rows('moves') if not ya('move', m['id'])]
paso('Asientos por cargar: %s' % len(pendientes))
creados = 0
for i in range(0, len(pendientes), 100):
    lote = pendientes[i:i + 100]
    vals_list = []
    for m in lote:
        vals = {
            'move_type': m['move_type'], 'name': m['name'], 'ref': m['ref'], 'date': m['date'],
            'journal_id': ya('journal', m['journal_id']), 'partner_id': contacto(m['partner_id']),
            'currency_id': moneda(m['currency_id']), 'company_id': company.id, 'narration': m['narration'],
            'line_ids': [Command.create(vals_linea(line)) for line in lineas_mv[m['id']]],
        }
        if m['move_type'] in FACTURAS:
            vals.update({'invoice_date': m['invoice_date'] or m['date'], 'invoice_date_due': m['invoice_date_due'],
                         'invoice_origin': m['invoice_origin'], 'payment_reference': m['payment_reference']})
            # En el origen la serie y el numero del DTE viven juntos en `ref`: SERIE-NUMERO.
            if m['ref'] and '-' in m['ref'] and m['move_type'] in TIPO_DTE:
                serie, numero = m['ref'].rsplit('-', 1)
                vals.update({'serie': serie.strip(), 'numero': numero.strip(), 'tipo_dte': TIPO_DTE[m['move_type']]})
        vals_list.append(vals)
    moves = Move.create(vals_list)
    for m, move in zip(lote, moves):
        anotar('move', m['id'], move)
        for src, new in zip(lineas_mv[m['id']], move.line_ids.sorted('id')):
            anotar('move_line', src['id'], new)
    por_estado = defaultdict(lambda: env['account.move'])
    for m, move in zip(lote, moves):
        por_estado[m['state']] |= move
    if por_estado['posted']:
        por_estado['posted'].with_context(skip_invoice_sync=True)._post(soft=False)
    if por_estado['cancel']:
        por_estado['cancel'].with_context(skip_invoice_sync=True).write({'state': 'cancel'})
    guardar_mapa()
    creados += len(lote)
    paso('  asientos %s / %s' % (creados, len(pendientes)))

# ---------------------------------------------------------------- conciliaciones
Partial = env['account.partial.reconcile']
grupos = defaultdict(list)
nuevas = 0
for p in rows('partials'):
    debe, haber = ya('move_line', p['debit_move_id']), ya('move_line', p['credit_move_id'])
    if not (debe and haber):
        continue
    rec_id = ya('partial', p['id'])
    if not rec_id:
        rec = Partial.create({
            'debit_move_id': debe, 'credit_move_id': haber, 'amount': p['amount'],
            'debit_amount_currency': p['debit_amount_currency'], 'credit_amount_currency': p['credit_amount_currency'],
        })
        anotar('partial', p['id'], rec)
        rec_id = rec.id
        nuevas += 1
    if p['full_reconcile_id']:
        grupos[p['full_reconcile_id']].append(rec_id)
guardar_mapa()

# Una conciliacion completa solo se cierra si TODAS sus lineas vinieron en esta carga.
lineas_full = defaultdict(list)
for line in rows('move_lines'):
    if line['full_reconcile_id']:
        lineas_full[line['full_reconcile_id']].append(line)
completas = 0
Full = env['account.full.reconcile']
for full_id, parciales in grupos.items():
    if ya('full', full_id):
        continue
    lineas = env['account.move.line'].browse([ya('move_line', l['id']) for l in lineas_full[full_id]])
    if lineas and all(lineas.mapped('reconciled')) and not any(lineas.mapped('full_reconcile_id')):
        anotar('full', full_id, Full.create({
            'partial_reconcile_ids': [Command.set(parciales)], 'reconciled_line_ids': [Command.set(lineas.ids)]}))
        completas += 1
guardar_mapa()
paso('Conciliaciones: %s parciales nuevas, %s completas' % (nuevas, completas))

# ---------------------------------------------------------------- archivos y mensajes
MODELO = {'purchase.order': 'purchase_order', 'sale.order': 'sale_order', 'account.move': 'move'}
tar_path = os.path.join(D, 'archivos.tar')
tar = tarfile.open(tar_path) if os.path.exists(tar_path) else None
Attachment = env['ir.attachment']
nuevas = faltan = 0
for a in rows('attachments'):
    if ya('attachment', a['id']):
        continue
    res_id = ya(MODELO.get(a['res_model'], ''), a['res_id'])
    if not res_id:
        continue
    try:
        contenido = tar.extractfile(a['store_fname']).read()
    except Exception:
        faltan += 1
        AVISOS['archivo que no estaba en el disco de origen'].append('%s (%s)' % (a['name'], a['store_fname']))
        continue
    rec = Attachment.create({
        'name': a['name'], 'res_model': a['res_model'], 'res_id': res_id, 'raw': contenido,
        'mimetype': a['mimetype'], 'description': a['description'], 'company_id': company.id,
    })
    if rec.checksum != a['checksum']:
        AVISOS['archivo cuyo contenido no coincide con el de origen'].append(a['name'])
    anotar('attachment', a['id'], rec)
    nuevas += 1
guardar_mapa()
paso('Archivos: %s nuevos, %s no estaban en el disco de origen' % (nuevas, faltan))

Message = env['mail.message']
nota = env.ref('mail.mt_note').id
comentario = env.ref('mail.mt_comment').id
nuevas = 0
for m in rows('messages'):
    if ya('message', m['id']):
        continue
    res_id = ya(MODELO.get(m['model'], ''), m['res_id'])
    if not res_id:
        continue
    rec = Message.create({
        'model': m['model'], 'res_id': res_id, 'message_type': 'comment',
        'subtype_id': nota if m['interno'] else comentario, 'body': m['body'] or '', 'subject': m['subject'],
        'author_id': contacto(m['author_id']), 'date': fh(m['date']),
        'attachment_ids': [Command.set([ya('attachment', x) for x in (m['attachment_ids'] or []) if ya('attachment', x)])],
    })
    anotar('message', m['id'], rec)
    nuevas += 1
guardar_mapa()
paso('Comentarios: %s nuevos' % nuevas)

# ---------------------------------------------------------------- cierre
env.flush_all()
print('\n=== AVISOS ===')
for motivo, casos in AVISOS.items():
    unicos = sorted(set(map(str, casos)))
    print('- %s: %s' % (motivo, len(unicos)))
    for caso in unicos[:8]:
        print('    · %s' % caso)
if CONFIRMAR:
    env.cr.commit()
    paso('CONFIRMADO en la base %s' % env.cr.dbname)
else:
    env.cr.rollback()
    paso('ENSAYO EN SECO: no se guardo nada (OZU_CONFIRMAR=1 para guardar)')
