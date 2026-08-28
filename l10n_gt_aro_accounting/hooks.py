# hooks.py
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Normaliza las retenciones de ISR creadas por la version anterior del modulo.

    Antes las lineas de retencion se identificaban por su texto ('ISR') y las
    cuentas vivian en parametros de sistema. Aqui se copian esas cuentas al nuevo
    tipo de retencion, se marcan las lineas historicas con el flag `es_retencion`
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

    # 1. Las cuentas configuradas antes pasan al tipo de retencion.
    valores = {}
    cuenta_proveedor = param.get_param('contabilidad_custom.isr_account_id')
    cuenta_cliente = param.get_param('contabilidad_custom.isr_account_client_id')
    if cuenta_proveedor and not tipo_isr.account_id:
        valores['account_id'] = int(cuenta_proveedor)
    if cuenta_cliente and not tipo_isr.account_client_id:
        valores['account_client_id'] = int(cuenta_cliente)
    if valores:
        tipo_isr.write(valores)

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
