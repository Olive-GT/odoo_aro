# hooks.py
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Normaliza las retenciones de ISR creadas por la version anterior del modulo.

    Antes las lineas de retencion se identificaban por su texto ('ISR') y las
    cuentas vivian en parametros de sistema. Aqui se asigna a cada empresa su
    cuenta en el nuevo tipo de retencion, se marcan las lineas historicas con el flag `es_retencion`
    y se crea el registro `retencion.aplicada` de cada factura.

    Los pasos 2 y 3 son de conveniencia, no de correccion: `_es_linea_retencion()`
    sigue reconociendo el formato anterior, asi que los libros fiscales dan el
    mismo resultado con o sin esta migracion. El hook es idempotente y no altera
    ningun importe contable, solo rellena columnas nuevas.
    """
    param = env['ir.config_parameter'].sudo()
    tipo_isr = env.ref('l10n_gt_aro_accounting.retencion_isr_compras', raise_if_not_found=False)
    if not tipo_isr:
        return

    # 1. Cada empresa conserva la cuenta de ISR que ya usaba. El parametro de
    #    sistema anterior era uno solo para toda la base, pero en una base con
    #    varias empresas cada una contabilizaba el ISR en su propia cuenta; por
    #    eso se lee de las facturas historicas y el parametro queda de respaldo.
    env.cr.execute("""
        SELECT am.company_id,
               am.move_type IN ('in_invoice', 'in_refund') AS es_compra,
               aml.account_id,
               COUNT(*) AS veces
          FROM account_move_line aml
          JOIN account_move am ON am.id = aml.move_id
         WHERE aml.display_type = 'product'
           AND aml.name = 'ISR'
           AND am.aplica_isr IS TRUE
           AND am.move_type IN ('in_invoice', 'in_refund', 'out_invoice', 'out_refund')
      GROUP BY am.company_id, es_compra, aml.account_id
      ORDER BY veces DESC
    """)
    for company_id, es_compra, account_id, _veces in env.cr.fetchall():
        tipo = tipo_isr.with_company(company_id)
        campo = 'account_id' if es_compra else 'account_client_id'
        if not tipo[campo]:
            tipo[campo] = account_id

    Account = env['account.account']
    for clave, campo in (('contabilidad_custom.isr_account_id', 'account_id'),
                         ('contabilidad_custom.isr_account_client_id', 'account_client_id')):
        valor = param.get_param(clave)
        cuenta = Account.browse(int(valor)).exists() if valor else Account
        for company in cuenta.company_ids:
            tipo = tipo_isr.with_company(company)
            if not tipo[campo]:
                tipo[campo] = cuenta

    if not param.get_param('contabilidad_custom.retencion_isr_tipo_id'):
        param.set_param('contabilidad_custom.retencion_isr_tipo_id', str(tipo_isr.id))

    # 2. Las lineas historicas se marcan con el flag. Se usa SQL porque las
    #    facturas ya estan publicadas y no admiten escritura por ORM.
    env.cr.execute("""
        UPDATE account_move_line aml
           SET es_retencion = TRUE
          FROM account_move am
         WHERE aml.move_id = am.id
           AND am.aplica_isr IS TRUE
           AND aml.display_type = 'product'
           AND aml.name = 'ISR'
           AND aml.es_retencion IS NOT TRUE
    """)
    marcadas = env.cr.rowcount

    # 3. Se crea la retencion aplicada que faltaba en cada factura historica.
    env.cr.execute("""
        SELECT aml.move_id, SUM(aml.balance)
          FROM account_move_line aml
          JOIN account_move am ON am.id = aml.move_id
     LEFT JOIN retencion_aplicada ra
            ON ra.move_id = am.id AND ra.tipo_id = %s
         WHERE aml.es_retencion IS TRUE
           AND am.aplica_isr IS TRUE
           AND ra.id IS NULL
      GROUP BY aml.move_id
    """, (tipo_isr.id,))
    filas = env.cr.fetchall()

    if filas:
        montos = dict(filas)
        valores_retencion = []
        for move in env['account.move'].browse(list(montos)):
            lineas_base = move.invoice_line_ids.filtered(lambda l: not l.es_retencion)
            valores_retencion.append({
                'move_id': move.id,
                'tipo_id': tipo_isr.id,
                'base': sum(lineas_base.mapped('price_subtotal')),
                'amount': abs(montos[move.id] or 0.0),
            })
        env['retencion.aplicada'].create(valores_retencion)

    _logger.info(
        "Retenciones: %s lineas historicas marcadas, %s retenciones migradas.",
        marcadas, len(filas))
