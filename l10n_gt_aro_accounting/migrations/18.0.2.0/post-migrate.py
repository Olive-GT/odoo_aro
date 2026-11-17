# migrations/18.0.2.0/post-migrate.py
from odoo import api, SUPERUSER_ID

from odoo.addons.l10n_gt_aro_accounting.hooks import post_init_hook


def migrate(cr, version):
    """Corre la normalizacion de retenciones al ACTUALIZAR desde una version anterior.

    `post_init_hook` solo se ejecuta en una instalacion nueva. Una base que ya
    tenia el modulo instalado (version 18.0.1.0) y lo actualiza nunca pasaba por
    el: las cuentas de ISR se quedaban en los parametros de sistema y las
    facturas historicas sin su `retencion.aplicada`. El hook es idempotente, asi
    que se reutiliza tal cual.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    post_init_hook(env)
